from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Object
from app.db.session import SessionLocal
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT, JOB_TYPE_INGEST_LOCAL_FILE
from app.jobs.types import JobHandler
from app.llm.embedding_text import build_embedding_text
from app.local.constants import POLICY_UPLOAD_COPY
from app.local.paths import LocalPathResolver
from app.resources.constants import (
    CONTENT_INGESTED_POLICY_KEY,
    CONTENT_INGESTED_REVISION_KEY,
)
from app.services.job_queue_service import JobQueueService
from app.services.local_file_sync_service import copy_local_file_to_upload
from app.services.representation_embedding_worker import (
    load_unembedded_chunk_targets,
    store_representation_embeddings,
)
from app.services.representation_service import RepresentationService


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


def handle_embed_object(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    text = _load_embedding_text(object_id, user_id)
    embedding = embedding_service.embed(text)
    _store_object_embedding(object_id, user_id, embedding)

    chunk_targets = load_unembedded_chunk_targets(object_id, user_id)
    if chunk_targets:
        chunk_embeddings = [
            (target.representation_id, embedding_service.embed(target.text))
            for target in chunk_targets
        ]
        store_representation_embeddings(object_id, user_id, chunk_embeddings)


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
        obj = lookup_session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")

        metadata = dict(obj.metadata_ or {})
        device_key = metadata.get("device_key")
        root_path = metadata.get("local_root_path")
        relative_path = metadata.get("local_relative_path")
        current_revision = metadata.get("content_revision")
        if not device_key or not root_path or not relative_path:
            raise ValueError("local object missing path metadata")

        if expected_revision is not None and current_revision != expected_revision:
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
        policy = expected_policy or metadata.get("indexing_policy")
        content_hash = metadata.get("content_hash")

        if policy == POLICY_UPLOAD_COPY:
            copied = copy_local_file_to_upload(
                source_path,
                upload_root,
                user_id,
                object_id,
                content_hash,
            )
            metadata["upload_path"] = str(copied)

        representation_service = RepresentationService(ingest_session, user_id)
        representation_service.ingest_file(object_id, source_path)

        obj = ingest_session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")
        merged = dict(obj.metadata_ or {})
        merged.update(metadata)
        if expected_revision is not None:
            merged[CONTENT_INGESTED_REVISION_KEY] = expected_revision
        if expected_policy is not None:
            merged[CONTENT_INGESTED_POLICY_KEY] = expected_policy
        obj.metadata_ = merged
        ingest_session.flush()

        job_queue = JobQueueService(ingest_session)
        job_queue.enqueue(
            JOB_TYPE_EMBED_OBJECT,
            {"object_id": str(object_id)},
            user_id=user_id,
        )
        ingest_session.commit()
    except Exception:
        ingest_session.rollback()
        raise
    finally:
        ingest_session.close()


HANDLERS: dict[str, JobHandler] = {
    JOB_TYPE_EMBED_OBJECT: handle_embed_object,
    JOB_TYPE_INGEST_LOCAL_FILE: handle_ingest_local_file,
}


def get_handler(job_type: str) -> JobHandler | None:
    return HANDLERS.get(job_type)
