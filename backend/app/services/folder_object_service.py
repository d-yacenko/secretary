"""Folder object mapping for registered local roots."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ObjectCreate
from app.db.models import LocalDevice, LocalRoot, Object
from app.local.constants import PROVIDER_LOCAL_DEVICE
from app.local.paths import normalize_relative_path
from app.services.correlation_constants import FOLDER_KIND
from app.services.graph_service import GraphService
from app.services.provenance import CONFIRMED_STATE


def build_folder_external_id(device_key: str, root_path: str) -> str:
    normalized = normalize_relative_path(root_path)
    return f"folder:{device_key}:{normalized}"


def folder_title_from_root_path(root_path: str) -> str:
    normalized = normalize_relative_path(root_path)
    name = Path(normalized).name
    return name or normalized or "Папка"


class FolderObjectService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id)

    def ensure_folder_for_root(self, device: LocalDevice, root: LocalRoot) -> Object:
        external_id = build_folder_external_id(device.device_key, root.root_path)
        existing = self._session.scalar(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.provider == PROVIDER_LOCAL_DEVICE,
                Object.external_id == external_id,
            )
        )
        if existing is not None:
            metadata = dict(existing.metadata_ or {})
            metadata.update(
                {
                    "device_key": device.device_key,
                    "local_root_path": root.root_path,
                    "default_policy": root.default_policy,
                }
            )
            existing.title = folder_title_from_root_path(root.root_path)
            existing.metadata_ = metadata
            self._session.flush()
            return existing

        metadata = {
            "device_key": device.device_key,
            "local_root_path": root.root_path,
            "default_policy": root.default_policy,
        }
        return self._graph.create_object(
            ObjectCreate(
                kind=FOLDER_KIND,
                title=folder_title_from_root_path(root.root_path),
                origin="user",
                state=CONFIRMED_STATE,
                provider=PROVIDER_LOCAL_DEVICE,
                external_id=external_id,
                metadata=metadata,
            )
        )

    def get_folder_for_root(self, device_key: str, root_path: str) -> Object | None:
        external_id = build_folder_external_id(device_key, root_path)
        return self._session.scalar(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.provider == PROVIDER_LOCAL_DEVICE,
                Object.external_id == external_id,
                Object.kind == FOLDER_KIND,
            )
        )
