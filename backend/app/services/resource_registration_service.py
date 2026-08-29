import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ResourceRegisterRequest
from app.db.models import Object
from app.llm.embedding_service import EmbeddingService
from app.resources.constants import (
    ALLOWED_UPLOAD_SUFFIXES,
    CLOUD_PROVIDERS,
    MAX_UPLOAD_BYTES,
    PROVIDER_UPLOAD,
    PROVIDER_WEB,
    REVISION_METADATA_KEYS,
)
from app.resources.web_fetch import WebFetchError, fetch_web_page
from app.services.db_errors import is_external_object_unique_violation
from app.services.embedding_index import refresh_object_embedding
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.job_queue_service import JobQueueService
from app.services.representation_service import RepresentationService


@dataclass(frozen=True)
class ResourceRegisterResult:
    object_id: UUID
    status: str
    kind: str
    title: str
    canonical_uri: str | None
    provider: str | None
    external_id: str | None
    jobs_enqueued: int
    representations_created: int


class ResourceRegistrationService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        job_queue: JobQueueService,
        embedding_service: EmbeddingService | None = None,
        upload_root: Path | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._job_queue = job_queue
        self._embedding_service = embedding_service
        self._upload_root = upload_root or Path("/tmp/secretary-uploads")

    def register(
        self,
        data: ResourceRegisterRequest,
        uploaded_path: Path | None = None,
    ) -> ResourceRegisterResult:
        provider = self._resolve_provider(data)
        external_id = self._resolve_external_id(data)
        metadata = dict(data.metadata)
        metadata.setdefault("registered_at", datetime.now().isoformat())
        if data.local_path_metadata:
            metadata["local_path_metadata"] = data.local_path_metadata

        revision = self._revision_signature(metadata)
        if revision is not None:
            metadata["content_revision"] = revision

        existing = self._find_existing(data.kind, provider, external_id, data.canonical_uri)
        if existing is not None and self._is_unchanged(existing, revision, data.ingest_content):
            return ResourceRegisterResult(
                object_id=existing.id,
                status="unchanged",
                kind=existing.kind,
                title=existing.title,
                canonical_uri=existing.canonical_uri,
                provider=existing.provider,
                external_id=existing.external_id,
                jobs_enqueued=0,
                representations_created=0,
            )

        created = existing is None
        obj = existing or self._create_object(data, provider, external_id, metadata)
        if not created:
            self._apply_metadata_update(obj, data, provider, external_id, metadata)

        content_changed = False
        representations_created = 0

        if data.text is not None:
            bounded = data.text[:8000]
            if obj.body != bounded:
                obj.body = bounded
                content_changed = True
            if data.ingest_content:
                representations_created = len(
                    self._representation_service().ingest_text_content(obj.id, bounded)
                )
                content_changed = True

        if uploaded_path is not None:
            if provider is None:
                provider = PROVIDER_UPLOAD
            if external_id is None:
                external_id = str(metadata.get("content_hash") or uploaded_path.name)
            obj.provider = provider
            obj.external_id = external_id
            stored_path = self._store_upload(obj.id, uploaded_path)
            metadata["upload_path"] = str(stored_path)
            metadata["upload_filename"] = uploaded_path.name
            obj.metadata_ = metadata
            if data.ingest_content:
                representations_created = len(
                    self._representation_service().ingest_file(obj.id, stored_path)
                )
                content_changed = True

        if data.kind == "web_page" and data.ingest_content and data.canonical_uri:
            try:
                fetched = fetch_web_page(data.canonical_uri)
            except WebFetchError as exc:
                raise ValidationError(exc.message) from exc
            if fetched.title and (created or obj.title == data.title):
                obj.title = fetched.title
            obj.body = fetched.text
            obj.canonical_uri = fetched.final_url
            metadata["fetched_at"] = datetime.now().isoformat()
            obj.metadata_ = metadata
            representations_created = len(
                self._representation_service().ingest_text_content(obj.id, fetched.text)
            )
            content_changed = True

        jobs_enqueued = 0
        if content_changed:
            if self._embedding_service is not None:
                refresh_object_embedding(obj, self._embedding_service)
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(obj.id)},
                user_id=self._user_id,
            )
            jobs_enqueued = 1

        self._session.flush()
        status = "created" if created else "updated"

        return ResourceRegisterResult(
            object_id=obj.id,
            status=status,
            kind=obj.kind,
            title=obj.title,
            canonical_uri=obj.canonical_uri,
            provider=obj.provider,
            external_id=obj.external_id,
            jobs_enqueued=jobs_enqueued,
            representations_created=representations_created,
        )

    def _representation_service(self) -> RepresentationService:
        return RepresentationService(
            self._session,
            self._user_id,
            embedding_service=self._embedding_service,
        )

    def _resolve_provider(self, data: ResourceRegisterRequest) -> str | None:
        if data.provider:
            return data.provider
        provider = data.metadata.get("provider")
        if isinstance(provider, str):
            return provider
        if data.kind == "web_page":
            return PROVIDER_WEB
        return None

    def _resolve_external_id(self, data: ResourceRegisterRequest) -> str | None:
        if data.external_id:
            return data.external_id
        external_id = data.metadata.get("external_id")
        if isinstance(external_id, str):
            return external_id
        return None

    def _revision_signature(self, metadata: dict[str, Any]) -> str | None:
        parts = {
            key: metadata[key]
            for key in REVISION_METADATA_KEYS
            if metadata.get(key) is not None
        }
        if not parts:
            return None
        return json.dumps(parts, sort_keys=True, default=str)

    def _find_existing(
        self,
        kind: str,
        provider: str | None,
        external_id: str | None,
        canonical_uri: str | None,
    ) -> Object | None:
        if provider and external_id:
            obj = self._session.scalar(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.provider == provider,
                    Object.kind == kind,
                    Object.external_id == external_id,
                )
            )
            if obj is not None:
                return obj
        if canonical_uri:
            return self._session.scalar(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.kind == kind,
                    Object.canonical_uri == canonical_uri,
                )
            )
        return None

    def _is_unchanged(
        self, obj: Object, revision: str | None, ingest_content: bool
    ) -> bool:
        if ingest_content:
            return False
        stored_revision = (obj.metadata_ or {}).get("content_revision")
        if revision is not None and stored_revision == revision:
            return True
        if revision is None and stored_revision is None:
            return False
        return False

    def _create_object(
        self,
        data: ResourceRegisterRequest,
        provider: str | None,
        external_id: str | None,
        metadata: dict[str, Any],
    ) -> Object:
        if provider in CLOUD_PROVIDERS and not external_id:
            raise ValidationError("cloud resources require external_id")
        obj = Object(
            user_id=self._user_id,
            kind=data.kind,
            title=data.title,
            origin="user",
            state="confirmed",
            body=data.text[:8000] if data.text else None,
            provider=provider,
            external_id=external_id,
            canonical_uri=data.canonical_uri,
            metadata_=metadata,
        )
        self._session.add(obj)
        try:
            self._session.flush()
        except Exception as exc:
            if is_external_object_unique_violation(exc):
                raise ConflictError("external object already exists") from exc
            raise
        return obj

    def _apply_metadata_update(
        self,
        obj: Object,
        data: ResourceRegisterRequest,
        provider: str | None,
        external_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        obj.title = data.title
        obj.canonical_uri = data.canonical_uri or obj.canonical_uri
        if provider:
            obj.provider = provider
        if external_id:
            obj.external_id = external_id
        obj.metadata_ = metadata

    def _store_upload(self, object_id: UUID, source_path: Path) -> Path:
        suffix = source_path.suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise ValidationError(f"unsupported upload format: {suffix}")
        size = source_path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise ValidationError("upload exceeds size limit")
        target_dir = self._upload_root / str(self._user_id) / str(object_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source_path.name
        target_path.write_bytes(source_path.read_bytes())
        return target_path

    def get_object_for_user(self, object_id: UUID) -> Object:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", object_id)
        return obj
