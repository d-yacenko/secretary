import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LocalDevice, LocalRoot, Object
from app.local.bounded_io import stream_content_hash
from app.local.constants import (
    DEFAULT_LOCAL_POLICY,
    LOCAL_POLICIES,
    MAX_REPORT_BATCH,
    MAX_SCAN_DEPTH,
    MAX_SCAN_INSPECTION_ITEMS,
    MAX_SCAN_SUPPORTED_ITEMS,
    POLICY_METADATA_ONLY,
    POLICY_UPLOAD_COPY,
    PROVIDER_LOCAL_DEVICE,
    SUPPORTED_LOCAL_SUFFIXES,
    build_local_external_id,
    build_personal_file_uri,
    infer_local_kind,
)
from app.local.device_keys import validate_device_key
from app.local.errors import LocalAccessError, LocalFileError
from app.local.paths import LocalPathResolver, normalize_relative_path
from app.resources.constants import (
    CONTENT_INGESTED_POLICY_KEY,
    CONTENT_INGESTED_REVISION_KEY,
    REVISION_METADATA_KEYS,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.job_queue_service import JobQueueService
from app.services.local_device_service import LocalDeviceService


@dataclass(frozen=True)
class LocalFileReport:
    relative_path: str
    size: int
    modified_at: str
    content_hash: str | None = None
    policy: str | None = None


@dataclass(frozen=True)
class LocalSyncResult:
    objects_created: int
    objects_updated: int
    objects_unchanged: int
    ingest_jobs_enqueued: int
    items_seen: int
    items_truncated: bool


class LocalFileSyncService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        path_resolver: LocalPathResolver,
        job_queue: JobQueueService,
        upload_root: Path | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._path_resolver = path_resolver
        self._job_queue = job_queue
        self._upload_root = upload_root
        self._device_service = LocalDeviceService(session, user_id, path_resolver)

    def scan_root(self, root_id: UUID) -> LocalSyncResult:
        root = self._device_service.get_root_for_user(root_id)
        device = self._session.get(LocalDevice, root.device_id)
        if device is None or device.user_id != self._user_id:
            raise LocalAccessError("device ownership mismatch")
        root_dir = self._path_resolver.resolve_root_path(
            self._user_id, device.device_key, root.root_path
        )
        if not root_dir.is_dir():
            raise ValidationError("registered root is not a directory")

        reports: list[LocalFileReport] = []
        truncated = False
        for file_path, walk_truncated in _bounded_supported_walk(
            root_dir,
            MAX_SCAN_DEPTH,
            MAX_SCAN_SUPPORTED_ITEMS,
            MAX_SCAN_INSPECTION_ITEMS,
        ):
            rel = file_path.relative_to(root_dir).as_posix()
            reports.append(_file_report_from_path(file_path, rel))
            truncated = walk_truncated
            if len(reports) >= MAX_SCAN_SUPPORTED_ITEMS:
                truncated = True
                break

        result = self._apply_reports(device, root, reports)
        return LocalSyncResult(
            objects_created=result.objects_created,
            objects_updated=result.objects_updated,
            objects_unchanged=result.objects_unchanged,
            ingest_jobs_enqueued=result.ingest_jobs_enqueued,
            items_seen=len(reports),
            items_truncated=truncated,
        )

    def report_files(
        self,
        device_key: str,
        root_path: str,
        files: list[LocalFileReport],
    ) -> LocalSyncResult:
        if len(files) > MAX_REPORT_BATCH:
            raise ValidationError("file report batch exceeds limit")
        device = self._device_service.get_device_for_user(device_key)
        normalized_root = normalize_relative_path(root_path)
        root = self._session.scalar(
            select(LocalRoot).where(
                LocalRoot.user_id == self._user_id,
                LocalRoot.device_id == device.id,
                LocalRoot.root_path == normalized_root,
            )
        )
        if root is None:
            raise NotFoundError("local_root", normalized_root)

        for item in files:
            if item.policy is not None and item.policy not in LOCAL_POLICIES:
                raise ValidationError(f"unsupported local policy: {item.policy}")

        result = self._apply_reports(device, root, files)
        return LocalSyncResult(
            objects_created=result.objects_created,
            objects_updated=result.objects_updated,
            objects_unchanged=result.objects_unchanged,
            ingest_jobs_enqueued=result.ingest_jobs_enqueued,
            items_seen=len(files),
            items_truncated=False,
        )

    def resolve_object_file_path(self, obj: Object) -> Path:
        if obj.user_id != self._user_id:
            raise LocalAccessError("object ownership mismatch")
        metadata = obj.metadata_ or {}
        device_key = metadata.get("device_key")
        root_path = metadata.get("local_root_path")
        relative_path = metadata.get("local_relative_path")
        if not device_key or not root_path or not relative_path:
            raise LocalFileError("object is missing local path metadata")
        return self._path_resolver.resolve_file_path(
            self._user_id,
            str(device_key),
            str(root_path),
            str(relative_path),
        )

    def _apply_reports(
        self,
        device: LocalDevice,
        root: LocalRoot,
        reports: list[LocalFileReport],
    ) -> LocalSyncResult:
        created = 0
        updated = 0
        unchanged = 0
        ingest_jobs = 0

        for item in reports:
            normalized_rel = normalize_relative_path(item.relative_path)
            policy = item.policy or root.default_policy
            if policy not in LOCAL_POLICIES:
                raise ValidationError(f"unsupported local policy: {policy}")

            metadata: dict[str, Any] = {
                "device_key": device.device_key,
                "local_root_path": root.root_path,
                "local_relative_path": normalized_rel,
                "filename": Path(normalized_rel).name,
                "size": item.size,
                "modified_at": item.modified_at,
                "indexing_policy": policy,
            }
            if item.content_hash:
                metadata["content_hash"] = item.content_hash

            revision = _revision_signature(metadata)
            if revision is not None:
                metadata["content_revision"] = revision

            external_id = build_local_external_id(
                device.device_key, root.root_path, normalized_rel
            )
            obj = self._session.scalar(
                select(Object).where(
                    Object.user_id == self._user_id,
                    Object.provider == PROVIDER_LOCAL_DEVICE,
                    Object.external_id == external_id,
                )
            )

            was_created = obj is None
            if was_created:
                metadata["registered_at"] = datetime.now().isoformat()
                suffix = Path(normalized_rel).suffix.lower()
                obj = Object(
                    user_id=self._user_id,
                    kind=infer_local_kind(suffix),
                    title=Path(normalized_rel).name,
                    origin="user",
                    state="confirmed",
                    provider=PROVIDER_LOCAL_DEVICE,
                    external_id=external_id,
                    canonical_uri=build_personal_file_uri(device.device_key, external_id),
                    metadata_=dict(metadata),
                )
                self._session.add(obj)
                self._session.flush()
                obj.canonical_uri = build_personal_file_uri(device.device_key, str(obj.id))
                created += 1
            else:
                prior_meta = obj.metadata_ or {}
                prior_revision = prior_meta.get("content_revision")
                merged = dict(prior_meta)
                merged.update(metadata)
                obj.title = Path(normalized_rel).name
                obj.kind = infer_local_kind(Path(normalized_rel).suffix.lower())
                obj.metadata_ = merged
                obj.canonical_uri = build_personal_file_uri(device.device_key, str(obj.id))

                if prior_revision == revision:
                    if not _needs_ingest(merged, revision, policy):
                        unchanged += 1
                        continue
                    if self._job_queue.has_pending_ingest_job(
                        obj.id, revision, policy, self._user_id
                    ):
                        unchanged += 1
                        continue
                else:
                    updated += 1

            if policy == POLICY_METADATA_ONLY:
                continue

            self._job_queue.enqueue(
                "ingest_local_file",
                {
                    "object_id": str(obj.id),
                    "expected_revision": revision,
                    "expected_policy": policy,
                },
                user_id=self._user_id,
            )
            ingest_jobs += 1

        self._session.flush()
        return LocalSyncResult(
            objects_created=created,
            objects_updated=updated,
            objects_unchanged=unchanged,
            ingest_jobs_enqueued=ingest_jobs,
            items_seen=len(reports),
            items_truncated=False,
        )


def _bounded_supported_walk(
    root_dir: Path,
    max_depth: int,
    max_supported: int,
    max_inspections: int,
):
    supported: list[Path] = []
    inspections = 0
    truncated = False
    stack: list[tuple[Path, int]] = [(root_dir, 0)]

    while stack:
        if inspections >= max_inspections:
            truncated = True
            break
        current, depth = stack.pop()
        if not current.is_dir():
            continue
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for child in reversed(children):
            inspections += 1
            if inspections > max_inspections:
                truncated = True
                break
            if child.is_dir() and depth < max_depth:
                stack.append((child, depth + 1))
            elif child.is_file():
                if child.suffix.lower() in SUPPORTED_LOCAL_SUFFIXES:
                    supported.append(child)
                    yield child, truncated
                    if len(supported) >= max_supported:
                        truncated = True
                        return
                if len(supported) >= max_supported:
                    truncated = True
                    return
        if truncated:
            break


def _needs_ingest(metadata: dict[str, Any], revision: str | None, policy: str) -> bool:
    if policy == POLICY_METADATA_ONLY:
        return False
    ingested_revision = metadata.get(CONTENT_INGESTED_REVISION_KEY)
    ingested_policy = metadata.get(CONTENT_INGESTED_POLICY_KEY)
    if ingested_revision != revision or ingested_policy != policy:
        return True
    if policy == POLICY_UPLOAD_COPY:
        upload_path = metadata.get("upload_path")
        return not upload_path or not Path(upload_path).is_file()
    return False


def _file_report_from_path(path: Path, relative_path: str) -> LocalFileReport:
    stat = path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    content_hash = stream_content_hash(path)
    return LocalFileReport(
        relative_path=relative_path,
        size=stat.st_size,
        modified_at=modified_at,
        content_hash=content_hash,
    )


def _revision_signature(metadata: dict[str, Any]) -> str | None:
    parts = {
        key: metadata[key]
        for key in REVISION_METADATA_KEYS
        if metadata.get(key) is not None
    }
    if not parts:
        return None
    return json.dumps(parts, sort_keys=True, default=str)


def copy_local_file_to_upload(
    source_path: Path,
    upload_root: Path,
    user_id: UUID,
    object_id: UUID,
    content_hash: str | None,
) -> Path:
    suffix = source_path.suffix.lower()
    target_dir = upload_root / str(user_id) / str(object_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    hash_part = content_hash or stream_content_hash(source_path)
    if hash_part is None:
        hash_part = hashlib.sha256(str(object_id).encode()).hexdigest()
    target_path = target_dir / f"{hash_part}{suffix}"
    if not target_path.is_file():
        shutil.copyfile(source_path, target_path)
    return target_path
