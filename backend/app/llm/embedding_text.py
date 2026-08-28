from typing import Any

from app.db.models import Object

EMBEDDING_DIMENSION = 1536

USEFUL_METADATA_KEYS = frozenset(
    {
        "from",
        "to",
        "subject",
        "tags",
        "label",
        "status",
        "category",
        "author",
        "source",
    }
)


def build_embedding_text(obj: Object) -> str:
    parts: list[str] = [obj.title]
    if obj.body:
        parts.append(obj.body)
    for key, value in obj.metadata_.items():
        if key.startswith("_") or key in {"raw", "html", "payload", "content"}:
            continue
        if key in USEFUL_METADATA_KEYS or _is_compact_value(value):
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _is_compact_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        return len(value) <= 200
    if isinstance(value, list):
        return len(value) <= 10 and all(isinstance(item, str) and len(item) <= 80 for item in value)
    return False

