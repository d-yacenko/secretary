"""Central tombstone visibility helpers for Secretary-local object deletion."""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement

from app.db.models import Object
from app.domain.task_lifecycle import TASK_STATUS_DELETED


def is_object_tombstoned(obj: Object) -> bool:
    return obj.deleted_at is not None


def object_is_active(column: type[Object] = Object) -> ColumnElement[bool]:
    return column.deleted_at.is_(None)


def object_active_sql_fragment() -> str:
    return "o.deleted_at IS NULL"


def restore_object_from_explicit_intake(obj: Object) -> bool:
    if obj.deleted_at is None:
        return False
    obj.deleted_at = None
    if obj.kind == "task" and obj.status == TASK_STATUS_DELETED:
        obj.status = None
    return True


def tombstone_object(obj: Object, *, when: datetime | None = None) -> bool:
    if obj.deleted_at is not None:
        return False
    obj.deleted_at = when or datetime.now(UTC)
    if obj.kind == "task":
        obj.status = TASK_STATUS_DELETED
    return True


def passive_sync_should_skip_existing(existing: Object) -> bool:
    return is_object_tombstoned(existing)
