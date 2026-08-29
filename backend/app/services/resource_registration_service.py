import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ResourceRegisterRequest
from app.db.models import Object
from app.resources.constants import (
    ALLOWED_UPLOAD_SUFFIXES,
    CLOUD_PROVIDERS,
    CONTENT_INGESTED_REVISION_KEY,
    MAX_REGISTER_TEXT_CHARS,
    MAX_UPLOAD_BYTES,
    PROVIDER_UPLOAD,
    PROVIDER_WEB,
    REVISION_METADATA_KEYS,
)
from app.resources.upload_staging import StagedUpload
from app.resources.web_fetch import WebFetchError, WebFetchResult, fetch_web_page
from app.services.db_errors import is_external_object_unique_violation
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


_METADATA_COMPARE_SKIP_KEYS = frozenset(
    {
        "content_revision",
        CONTENT_INGESTED_REVISION_KEY,
        "registered_at",
        "fetched_at",
        "upload_path",
    }
)


class ResourceRegistrationService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        job_queue: JobQueueService,
        upload_root: Path | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._job_queue = job_queue
        self._upload_root = upload_root or Path("/tmp/secretary-uploads")

    def register(
        self,
        data: ResourceRegisterRequest,
        staged_upload: StagedUpload | None = None,
    ) -> ResourceRegisterResult:
        provider = self._resolve_provider(data)
        external_id = self._resolve_external_id(data)
        metadata = dict(data.metadata)
        metadata.setdefault("registered_at", datetime.now().isoformat())
        if data.local_path_metadata:
            metadata["local_path_metadata"] = data.local_path_metadata

        if staged_upload is not None:
            metadata["content_hash"] = staged_upload.content_hash
            metadata["upload_filename"] = staged_upload.original_filename
            if provider is None:
                provider = PROVIDER_UPLOAD
            if external_id is None:
                external_id = staged_upload.content_hash

        if data.text and not any(metadata.get(key) for key in REVISION_METADATA_KEYS):
            metadata.setdefault(
                "content_hash",
                hashlib.sha256(data.text.encode("utf-8")).hexdigest(),
            )

        if data.text is not None and len(data.text) > MAX_REGISTER_TEXT_CHARS:
            raise ValidationError("register text exceeds size limit")

        revision = self._revision_signature(metadata)
        if revision is not None:
            metadata["content_revision"] = revision

        existing = self._find_existing(
            data.kind, provider, external_id, data.canonical_uri, revision
        )
        metadata_changed = (
            existing is not None and self._metadata_differs(existing, data, metadata)
        )
        same_revision = (
            existing is not None
            and revision is not None
            and (existing.metadata_ or {}).get("content_revision") == revision
        )

        if existing is not None and same_revision and not metadata_changed:
            if not data.ingest_content or self._revision_already_ingested(existing, revision):
                return self._unchanged_result(existing)

        fetched: WebFetchResult | None = None
        needs_web_ingest = (
            data.kind == "web_page"
            and data.ingest_content
            and data.canonical_uri
            and (
                existing is None
                or not self._revision_already_ingested(existing, revision)
            )
        )
        if needs_web_ingest:
            self._ensure_no_open_transaction()
            try:
                fetched = fetch_web_page(data.canonical_uri)
            except WebFetchError as exc:
                raise ValidationError(exc.message) from exc

        created = existing is None
        obj = existing or self._create_object(data, provider, external_id, metadata)
        if not created:
            self._apply_metadata_update(obj, data, provider, external_id, metadata)

        ingested_marker = (obj.metadata_ or {}).get(CONTENT_INGESTED_REVISION_KEY)
        should_ingest = data.ingest_content and not self._revision_already_ingested(
            obj, revision
        )
        if ingested_marker is not None:
            metadata.setdefault(CONTENT_INGESTED_REVISION_KEY, ingested_marker)

        content_changed = False
        representations_created = 0

        if data.text is not None:
            bounded = data.text
            if obj.body != bounded:
                obj.body = bounded
            if should_ingest and bounded:
                representations_created = len(
                    self._representation_service().ingest_text_content(obj.id, bounded)
                )
                content_changed = True

        if staged_upload is not None and should_ingest:
            stored_path = self._store_upload(obj.id, staged_upload)
            metadata["upload_path"] = str(stored_path)
            metadata["upload_filename"] = staged_upload.original_filename
            obj.provider = provider or PROVIDER_UPLOAD
            obj.external_id = external_id or staged_upload.content_hash
            representations_created = len(
                self._representation_service().ingest_file(obj.id, stored_path)
            )
            content_changed = True

        if fetched is not None and should_ingest:
            if fetched.title and (created or obj.title == data.title):
                obj.title = fetched.title
            obj.body = fetched.text
            obj.canonical_uri = fetched.final_url
            metadata["fetched_at"] = datetime.now().isoformat()
            representations_created = len(
                self._representation_service().ingest_text_content(obj.id, fetched.text)
            )
            content_changed = True

        if content_changed and revision is not None:
            metadata[CONTENT_INGESTED_REVISION_KEY] = revision

        obj.metadata_ = dict(metadata)

        jobs_enqueued = 0
        if content_changed:
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(obj.id)},
                user_id=self._user_id,
            )
            jobs_enqueued = 1

        self._session.flush()

        if created:
            status = "created"
        elif content_changed or metadata_changed:
            status = "updated"
        else:
            status = "unchanged"

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

    def _unchanged_result(self, obj: Object) -> ResourceRegisterResult:
        return ResourceRegisterResult(
            object_id=obj.id,
            status="unchanged",
            kind=obj.kind,
            title=obj.title,
            canonical_uri=obj.canonical_uri,
            provider=obj.provider,
            external_id=obj.external_id,
            jobs_enqueued=0,
            representations_created=0,
        )

    def _ensure_no_open_transaction(self) -> None:
        if self._session.in_transaction():
            self._session.commit()

    def _representation_service(self) -> RepresentationService:
        return RepresentationService(self._session, self._user_id)

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

    def _revision_already_ingested(self, obj: Object, revision: str | None) -> bool:
        ingested = (obj.metadata_ or {}).get(CONTENT_INGESTED_REVISION_KEY)
        if revision is None:
            return ingested is not None
        return ingested == revision

    def _metadata_differs(
        self,
        obj: Object,
        data: ResourceRegisterRequest,
        metadata: dict[str, Any],
    ) -> bool:
        if obj.title != data.title:
            return True
        if data.canonical_uri is not None and obj.canonical_uri != data.canonical_uri:
            return True
        old_meta = {
            key: value
            for key, value in (obj.metadata_ or {}).items()
            if key not in _METADATA_COMPARE_SKIP_KEYS
        }
        new_meta = {
            key: value
            for key, value in metadata.items()
            if key not in _METADATA_COMPARE_SKIP_KEYS
        }
        return old_meta != new_meta

    def _find_existing(
        self,
        kind: str,
        provider: str | None,
        external_id: str | None,
        canonical_uri: str | None,
        revision: str | None = None,
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
            obj = self._session.scalar(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.kind == kind,
                    Object.canonical_uri == canonical_uri,
                )
            )
            if obj is not None:
                return obj
        if revision is not None:
            for candidate in self._session.scalars(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.kind == kind,
                )
            ).all():
                stored_revision = (candidate.metadata_ or {}).get("content_revision")
                if stored_revision == revision:
                    return candidate
        return None

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
            body=data.text if data.text else None,
            provider=provider,
            external_id=external_id,
            canonical_uri=data.canonical_uri,
            metadata_=dict(metadata),
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

    def _store_upload(self, object_id: UUID, staged: StagedUpload) -> Path:
        suffix = Path(staged.original_filename).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise ValidationError(f"unsupported upload format: {suffix or '(none)'}")
        if staged.size > MAX_UPLOAD_BYTES:
            raise ValidationError("upload exceeds size limit")
        target_dir = self._upload_root / str(self._user_id) / str(object_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / staged.original_filename
        shutil.copyfile(staged.path, target_path)
        return target_path

    def get_object_for_user(self, object_id: UUID) -> Object:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", object_id)
        return obj
