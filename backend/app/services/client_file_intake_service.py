"""Client-assisted local file intake into canonical objects."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LocalRoot, Object
from app.local.client_paths import (
    build_client_source_external_id,
    cheap_content_hash,
    normalize_client_source_path,
)
from app.local.constants import (
    POLICY_INDEX_TEXT,
    POLICY_METADATA_ONLY,
    PROVIDER_LOCAL_DEVICE,
    build_local_external_id,
    build_personal_file_uri,
    infer_local_kind,
)
from app.local.paths import normalize_relative_path
from app.services.client_representation_service import ClientRepresentationPersistence
from app.services.errors import NotFoundError, ValidationError
from app.services.folder_containment_service import FolderContainmentService
from app.services.folder_object_service import FolderObjectService
from app.services.local_device_service import LocalDeviceService
from app.services.pipeline_enqueue import enqueue_embed_object, enqueue_summarize_resource
from app.services.semantic_summary_service import invalidate_semantic_summary_metadata


@dataclass(frozen=True)
class ClientFileIntakeResult:
    object_id: UUID
    status: str
    jobs_enqueued: int
    representations_created: int
    metadata_only: bool


class ClientFileIntakeService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        device_service: LocalDeviceService,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._devices = device_service
        self._representations = ClientRepresentationPersistence(session, user_id)

    def intake(
        self,
        device_key: str,
        source_path: str,
        filename: str,
        size: int,
        modified_at: str,
        content_revision: str,
        representations: list[dict] | None = None,
        content_hash: str | None = None,
        metadata_only: bool = False,
        root_path: str | None = None,
        client_absolute_path: str | None = None,
    ) -> ClientFileIntakeResult:
        device = self._devices.get_device_for_user(device_key)
        if device is None:
            raise NotFoundError("local_device", device_key)

        normalized_root: str | None = None
        normalized_rel: str | None = None
        if root_path:
            normalized_root = normalize_relative_path(root_path)
            normalized_rel = normalize_relative_path(source_path)
            external_id = build_local_external_id(
                device_key, normalized_root, normalized_rel
            )
            client_path = normalize_client_source_path(
                client_absolute_path or source_path
            )
        else:
            client_path = normalize_client_source_path(source_path)
            external_id = build_client_source_external_id(device_key, client_path)

        filename_value = Path(filename).name if root_path else filename
        suffix = Path(filename_value).suffix.lower()
        kind = infer_local_kind(suffix) if suffix in {".txt", ".md", ".csv"} else "file"
        if suffix in {".txt", ".md"}:
            kind = "document"
        elif suffix == ".csv":
            kind = "dataset"

        reps = representations or []
        has_content = not metadata_only and len(reps) > 0

        existing = self._session.scalar(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.provider == PROVIDER_LOCAL_DEVICE,
                Object.external_id == external_id,
            )
        )

        if existing is not None and has_content:
            prior_meta = existing.metadata_ or {}
            prior_revision = prior_meta.get("content_revision")
            if prior_revision and prior_revision != content_revision:
                stored_mtime = prior_meta.get("modified_at")
                stored_size = prior_meta.get("size")
                if stored_mtime == modified_at and stored_size == size:
                    raise ValidationError("stale client representation revision")

        metadata: dict[str, Any] = {
            "device_key": device_key,
            "client_source_path": client_path,
            "filename": filename_value,
            "size": size,
            "modified_at": modified_at,
            "content_revision": content_revision,
            "indexing_policy": (
                POLICY_METADATA_ONLY if metadata_only else POLICY_INDEX_TEXT
            ),
            "registered_at": datetime.now(UTC).isoformat(),
        }
        if normalized_root and normalized_rel:
            metadata["local_root_path"] = normalized_root
            metadata["local_relative_path"] = normalized_rel
        if content_hash:
            metadata["content_hash"] = content_hash

        created = existing is None

        if existing is None:
            obj = Object(
                user_id=self._user_id,
                kind=kind,
                title=filename_value,
                origin="user",
                state="confirmed",
                provider=PROVIDER_LOCAL_DEVICE,
                external_id=external_id,
                canonical_uri=build_personal_file_uri(device_key, external_id),
                metadata_=dict(metadata),
            )
            self._session.add(obj)
            self._session.flush()
            obj.canonical_uri = build_personal_file_uri(device_key, str(obj.id))
        else:
            prior_meta = existing.metadata_ or {}
            prior_revision = prior_meta.get("content_revision")
            merged = dict(prior_meta)
            if prior_revision != content_revision:
                merged = invalidate_semantic_summary_metadata(merged)
            merged.update(metadata)
            existing.title = filename_value
            existing.kind = kind
            existing.metadata_ = merged
            existing.canonical_uri = build_personal_file_uri(device_key, str(existing.id))
            obj = existing

        prior_revision = (obj.metadata_ or {}).get("content_revision")
        same_revision = not created and prior_revision == content_revision

        representations_created = 0
        content_changed = False
        if has_content:
            if not same_revision or not self._has_client_representations(obj.id):
                representations_created = self._representations.replace_for_object(
                    obj.id, reps
                )
                content_changed = True
        elif metadata_only and created:
            content_changed = False

        if normalized_root:
            root = self._session.scalar(
                select(LocalRoot).where(
                    LocalRoot.user_id == self._user_id,
                    LocalRoot.device_id == device.id,
                    LocalRoot.root_path == normalized_root,
                )
            )
            if root is None:
                raise NotFoundError("local_root", normalized_root)
            folder_objects = FolderObjectService(self._session, self._user_id)
            folder_obj = folder_objects.ensure_folder_for_root(device, root)
            FolderContainmentService(self._session, self._user_id).link_files_to_folder(
                folder_obj.id, [obj.id]
            )

        jobs_enqueued = 0
        needs_reps = has_content and (
            created or not same_revision or not self._has_client_representations(obj.id)
        )
        if needs_reps:
            enqueue_summarize_resource(
                self._session, obj.id, self._user_id, content_revision
            )
            jobs_enqueued = 1
        elif (created or not same_revision) and (metadata_only or not has_content):
            enqueue_embed_object(self._session, obj.id, self._user_id)
            jobs_enqueued = 1

        if created:
            status = "created"
        elif content_changed or not same_revision:
            status = "updated"
        else:
            status = "unchanged"

        self._session.flush()
        return ClientFileIntakeResult(
            object_id=obj.id,
            status=status,
            jobs_enqueued=jobs_enqueued,
            representations_created=representations_created,
            metadata_only=metadata_only or not has_content,
        )

    def _has_client_representations(self, object_id: UUID) -> bool:
        from app.db.models import Representation

        row = self._session.scalar(
            select(Representation.id).where(Representation.object_id == object_id).limit(1)
        )
        return row is not None

    @staticmethod
    def build_revision(
        source_path: str,
        size: int,
        modified_at: str,
        content_hash: str | None = None,
        root_path: str | None = None,
    ) -> str:
        path_key = (
            f"{normalize_relative_path(root_path)}/{normalize_relative_path(source_path)}"
            if root_path
            else normalize_client_source_path(source_path)
        )
        parts = {
            "source_path": path_key,
            "size": size,
            "modified_at": modified_at,
        }
        if content_hash:
            parts["content_hash"] = content_hash
        return cheap_content_hash(
            "|".join(f"{key}={parts[key]}" for key in sorted(parts)).encode("utf-8")
        )
