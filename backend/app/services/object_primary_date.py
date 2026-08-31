"""Primary search/sort date for objects (aligned with Flutter object_dates)."""

from datetime import datetime

from app.db.models import Object


def _parse_metadata_modified_at(metadata: dict) -> datetime | None:
    raw = metadata.get("modified_at")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def object_primary_search_datetime(obj: Object) -> datetime | None:
    kind = obj.kind
    if kind == "task":
        return obj.due_at or obj.updated_at
    if kind in {"event", "calendar_event"}:
        return obj.start_at or obj.occurred_at or obj.updated_at
    if kind in {"email", "message", "chat", "chat_message"}:
        return obj.occurred_at or obj.updated_at
    if kind in {"file", "document", "dataset"}:
        modified = _parse_metadata_modified_at(dict(obj.metadata_ or {}))
        return modified or obj.occurred_at or obj.updated_at
    return obj.occurred_at or obj.updated_at
