from pathlib import Path
from uuid import UUID

from app.local.errors import LocalPathError


def normalize_relative_path(raw_path: str) -> str:
    if not raw_path or not raw_path.strip():
        raise LocalPathError("path must not be empty")
    if "\0" in raw_path:
        raise LocalPathError("path contains invalid characters")
    normalized = raw_path.replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise LocalPathError("path must not contain parent segments")
    if not parts:
        raise LocalPathError("path must not be empty")
    return "/".join(parts)


class LocalPathResolver:
    def __init__(self, mirror_root: Path | str) -> None:
        self._mirror_root = Path(mirror_root).resolve()

    def device_mirror_root(self, user_id: UUID, device_key: str) -> Path:
        return self._mirror_root / str(user_id) / device_key

    def resolve_root_path(self, user_id: UUID, device_key: str, root_path: str) -> Path:
        normalized = normalize_relative_path(root_path)
        base = self.device_mirror_root(user_id, device_key)
        resolved = (base / normalized).resolve()
        if not _is_under(resolved, base.resolve()):
            raise LocalPathError("root path escapes device mirror")
        return resolved

    def resolve_file_path(
        self,
        user_id: UUID,
        device_key: str,
        root_path: str,
        relative_path: str,
    ) -> Path:
        normalized_root = normalize_relative_path(root_path)
        normalized_file = normalize_relative_path(relative_path)
        base = self.device_mirror_root(user_id, device_key)
        resolved = (base / normalized_root / normalized_file).resolve()
        root_resolved = (base / normalized_root).resolve()
        if not _is_under(resolved, root_resolved):
            raise LocalPathError("file path escapes registered root")
        if not _is_under(resolved, base.resolve()):
            raise LocalPathError("file path escapes device mirror")
        return resolved


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
