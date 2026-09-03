from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_audit.constants import (
    WORKLOAD_BACKGROUND_CORRELATION,
    WORKLOAD_BACKGROUND_SUMMARY,
    WORKLOAD_EMBEDDING,
)
from app.ai_audit.context import ai_trace_session
from app.content_extraction.extract_service import build_explicit_resource_content_extractor
from app.core.assistant_openai_config import AssistantOpenAIConfigError
from app.core.config import settings
from app.db.models import Object
from app.db.session import SessionLocal
from app.jobs.constants import (
    JOB_TYPE_CORRELATE_OBJECT,
    JOB_TYPE_EMBED_OBJECT,
    JOB_TYPE_EXTRACT_EXPLICIT_RESOURCE_CONTENT,
    JOB_TYPE_INGEST_LOCAL_FILE,
    JOB_TYPE_SUMMARIZE_RESOURCE,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
    JOB_TYPE_SYNC_MATTERMOST,
    JOB_TYPE_SYNC_YANDEX_CALENDAR,
    JOB_TYPE_SYNC_YANDEX_MAIL,
)
from app.jobs.source_sync_handlers import (
    handle_sync_google_calendar,
    handle_sync_google_gmail,
    handle_sync_mattermost,
    handle_sync_yandex_calendar,
    handle_sync_yandex_mail,
)
from app.jobs.types import JobHandler
from app.llm.correlation_judge import create_correlation_judge_from_effective
from app.llm.embedding_service import create_embedding_service_for_api_key
from app.llm.embedding_text import build_embedding_text
from app.llm.openai_summarizer import create_openai_summarizer_from_effective
from app.local.constants import POLICY_UPLOAD_COPY
from app.local.paths import LocalPathResolver
from app.resources.constants import (
    CONTENT_INGESTED_POLICY_KEY,
    CONTENT_INGESTED_REVISION_KEY,
)
from app.services.background_ai_errors import BackgroundAIConfigurationError
from app.services.correlation_service import CorrelationService
from app.services.effective_user_settings_service import (
    EffectiveUserSettings,
    EffectiveUserSettingsService,
)
from app.services.local_file_sync_service import copy_local_file_to_upload
from app.services.pipeline_enqueue import (
    enqueue_correlate_object,
    enqueue_embed_object,
    enqueue_summarize_resource,
)
from app.services.representation_embedding_worker import (
    load_unembedded_chunk_targets,
    store_representation_embeddings,
)
from app.services.representation_service import RepresentationService
from app.services.semantic_summary_service import SemanticSummaryService


def _load_embedding_text(object_id: UUID, user_id: UUID) -> str:
    session = SessionLocal()
    try:
        obj = session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")
        return build_embedding_text(obj)
    finally:
        session.close()


def _store_object_embedding(object_id: UUID, user_id: UUID, embedding: list[float]) -> None:
    session = SessionLocal()
    try:
        obj = session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")
        obj.embedding = embedding
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ingest_already_complete(
    metadata: dict,
    expected_revision: str | None,
    expected_policy: str | None,
) -> bool:
    if metadata.get(CONTENT_INGESTED_REVISION_KEY) != expected_revision:
        return False
    if metadata.get(CONTENT_INGESTED_POLICY_KEY) != expected_policy:
        return False
    if expected_policy == POLICY_UPLOAD_COPY:
        upload_path = metadata.get("upload_path")
        return bool(upload_path and Path(upload_path).is_file())
    return True


def _revision_and_policy_match(
    metadata: dict,
    expected_revision: str | None,
    expected_policy: str | None,
) -> bool:
    if expected_revision is not None and metadata.get("content_revision") != expected_revision:
        return False
    return not (expected_policy is not None and metadata.get("indexing_policy") != expected_policy)


def _load_user_object(session: Session, object_id: UUID, user_id: UUID) -> Object | None:
    return session.scalar(
        select(Object).where(Object.id == object_id, Object.user_id == user_id)
    )


def _background_effective_settings(session: Session, user_id: UUID) -> EffectiveUserSettings:
    try:
        return EffectiveUserSettingsService.build(session).get_effective_settings(user_id)
    except AssistantOpenAIConfigError as exc:
        raise BackgroundAIConfigurationError(str(exc)) from exc


def _parent_trace_id_from_payload(payload: dict) -> UUID | None:
    raw = payload.get("parent_trace_id")
    if not raw:
        return None
    return UUID(str(raw))


def handle_embed_object(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    parent_trace_id = _parent_trace_id_from_payload(payload)
    with ai_trace_session(
        user_id,
        WORKLOAD_EMBEDDING,
        object_id=object_id,
        parent_trace_id=parent_trace_id,
    ):
        service = embedding_service
        if service is None:
            settings_service = EffectiveUserSettingsService.build(session)
            api_key = settings_service.resolve_openai_api_key(user_id)
            service = create_embedding_service_for_api_key(api_key)
        text = _load_embedding_text(object_id, user_id)
        embedding = service.embed(text)
        _store_object_embedding(object_id, user_id, embedding)

        chunk_targets = load_unembedded_chunk_targets(object_id, user_id)
        if chunk_targets:
            chunk_embeddings = [
                (target.representation_id, service.embed(target.text))
                for target in chunk_targets
            ]
            store_representation_embeddings(object_id, user_id, chunk_embeddings)

        lookup_session = SessionLocal()
        try:
            obj = lookup_session.scalar(
                select(Object).where(Object.id == object_id, Object.user_id == user_id)
            )
            if obj is not None:
                enqueue_correlate_object(lookup_session, object_id, user_id, obj.kind)
                lookup_session.commit()
        finally:
            lookup_session.close()


def handle_summarize_resource(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    expected_revision = payload.get("expected_revision")
    parent_trace_id = _parent_trace_id_from_payload(payload)
    with ai_trace_session(
        user_id,
        WORKLOAD_BACKGROUND_SUMMARY,
        object_id=object_id,
        parent_trace_id=parent_trace_id,
    ):
        lookup_session = SessionLocal()
        try:
            obj = lookup_session.scalar(
                select(Object).where(Object.id == object_id, Object.user_id == user_id)
            )
            if obj is None:
                raise ValueError(f"object ownership mismatch: {object_id}")
            metadata = obj.metadata_ or {}
            if expected_revision is not None and metadata.get("content_revision") != expected_revision:
                return
            effective = _background_effective_settings(lookup_session, user_id)
            summarizer = create_openai_summarizer_from_effective(effective)
            summary = SemanticSummaryService(
                lookup_session, user_id, summarizer=summarizer
            ).update_summary_for_object(object_id)
            if summary is not None:
                enqueue_embed_object(lookup_session, object_id, user_id)
            lookup_session.commit()
        finally:
            lookup_session.close()


def handle_correlate_object(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    parent_trace_id = _parent_trace_id_from_payload(payload)
    with ai_trace_session(
        user_id,
        WORKLOAD_BACKGROUND_CORRELATION,
        object_id=object_id,
        parent_trace_id=parent_trace_id,
    ):
        work_session = SessionLocal()
        try:
            effective = _background_effective_settings(session, user_id)
            judge = create_correlation_judge_from_effective(effective)
            CorrelationService(work_session, user_id, judge).run_correlation(object_id)
            work_session.commit()
        finally:
            work_session.close()


def handle_ingest_local_file(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    expected_revision = payload.get("expected_revision")
    expected_policy = payload.get("expected_policy")
    path_resolver = LocalPathResolver(Path(settings.local_files_root))
    upload_root = Path(settings.resource_upload_root)

    lookup_session = SessionLocal()
    try:
        obj = _load_user_object(lookup_session, object_id, user_id)
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")

        metadata = dict(obj.metadata_ or {})
        device_key = metadata.get("device_key")
        root_path = metadata.get("local_root_path")
        relative_path = metadata.get("local_relative_path")
        if not device_key or not root_path or not relative_path:
            raise ValueError("local object missing path metadata")

        if not _revision_and_policy_match(metadata, expected_revision, expected_policy):
            return

        if expected_policy and _ingest_already_complete(
            metadata, expected_revision, expected_policy
        ):
            return
    finally:
        lookup_session.close()

    source_path = path_resolver.resolve_file_path(
        user_id,
        str(device_key),
        str(root_path),
        str(relative_path),
    )
    if not source_path.is_file():
        raise ValueError(f"local file not found: {relative_path}")

    ingest_session = SessionLocal()
    try:
        obj = _load_user_object(ingest_session, object_id, user_id)
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")

        metadata = dict(obj.metadata_ or {})
        if not _revision_and_policy_match(metadata, expected_revision, expected_policy):
            return

        policy = expected_policy or metadata.get("indexing_policy")
        pending_upload_path: str | None = None
        pending_content_hash: str | None = None

        if policy == POLICY_UPLOAD_COPY:
            copied, content_hash, _ = copy_local_file_to_upload(
                source_path,
                upload_root,
                user_id,
                object_id,
            )
            pending_upload_path = str(copied)
            pending_content_hash = content_hash

        ingest_session.refresh(obj)
        metadata = dict(obj.metadata_ or {})
        if not _revision_and_policy_match(metadata, expected_revision, expected_policy):
            return

        representation_service = RepresentationService(ingest_session, user_id)
        representation_service.ingest_file(object_id, source_path)

        ingest_session.refresh(obj)
        metadata = dict(obj.metadata_ or {})
        if not _revision_and_policy_match(metadata, expected_revision, expected_policy):
            ingest_session.rollback()
            return

        merged = dict(metadata)
        if pending_upload_path is not None:
            merged["upload_path"] = pending_upload_path
        if pending_content_hash is not None:
            merged["content_hash"] = pending_content_hash
        if expected_revision is not None:
            merged[CONTENT_INGESTED_REVISION_KEY] = expected_revision
        if expected_policy is not None:
            merged[CONTENT_INGESTED_POLICY_KEY] = expected_policy
        obj.metadata_ = merged
        ingest_session.flush()

        revision = merged.get("content_revision")
        enqueue_summarize_resource(ingest_session, obj.id, user_id, revision)
        ingest_session.commit()
    except Exception:
        ingest_session.rollback()
        raise
    finally:
        ingest_session.close()


def handle_extract_explicit_resource_content(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    expected_revision = payload.get("expected_content_revision")
    extraction_version = payload.get("extraction_version")

    work_session = SessionLocal()
    extractor = build_explicit_resource_content_extractor(work_session, user_id)
    try:
        extractor.run(object_id, expected_revision, extraction_version)
        work_session.commit()
    except Exception:
        work_session.rollback()
        raise
    finally:
        extractor.close()
        work_session.close()


HANDLERS: dict[str, JobHandler] = {
    JOB_TYPE_EMBED_OBJECT: handle_embed_object,
    JOB_TYPE_INGEST_LOCAL_FILE: handle_ingest_local_file,
    JOB_TYPE_EXTRACT_EXPLICIT_RESOURCE_CONTENT: handle_extract_explicit_resource_content,
    JOB_TYPE_SUMMARIZE_RESOURCE: handle_summarize_resource,
    JOB_TYPE_CORRELATE_OBJECT: handle_correlate_object,
    JOB_TYPE_SYNC_GOOGLE_GMAIL: handle_sync_google_gmail,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR: handle_sync_google_calendar,
    JOB_TYPE_SYNC_YANDEX_MAIL: handle_sync_yandex_mail,
    JOB_TYPE_SYNC_YANDEX_CALENDAR: handle_sync_yandex_calendar,
    JOB_TYPE_SYNC_MATTERMOST: handle_sync_mattermost,
}


def get_handler(job_type: str) -> JobHandler | None:
    return HANDLERS.get(job_type)
