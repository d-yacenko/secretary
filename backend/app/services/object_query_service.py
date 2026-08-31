"""Deterministic structured object queries (no embeddings / LLM)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import nulls_last, or_, select
from sqlalchemy.orm import Session

from app.db.models import Object
from app.domain.task_lifecycle import TASK_STATUS_DELETED
from app.services.errors import ValidationError
from app.services.provenance import REJECTED_STATE
from app.tools.datetime_utils import normalize_tool_datetime

MAX_QUERY_OBJECTS_LIMIT = 50
DEFAULT_QUERY_OBJECTS_LIMIT = 20

ALLOWED_SORT_FIELDS = frozenset(
    {"due_at", "start_at", "occurred_at", "created_at", "updated_at", "title"}
)


class ObjectQueryService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def query(
        self,
        *,
        kinds: list[str] | None = None,
        providers: list[str] | None = None,
        statuses: list[str] | None = None,
        states: list[str] | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = DEFAULT_QUERY_OBJECTS_LIMIT,
    ) -> list[Object]:
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValidationError(f"invalid sort_by: {sort_by}")
        if sort_order not in {"asc", "desc"}:
            raise ValidationError("sort_order must be asc or desc")

        row_limit = max(1, min(limit, MAX_QUERY_OBJECTS_LIMIT))

        stmt = select(Object).where(
            Object.user_id == self._user_id,
            Object.state != REJECTED_STATE,
            or_(
                Object.kind != "task",
                Object.status.is_(None),
                Object.status != TASK_STATUS_DELETED,
            ),
        )

        if kinds:
            stmt = stmt.where(Object.kind.in_(kinds))
        if providers:
            stmt = stmt.where(Object.provider.in_(providers))
        if statuses:
            stmt = stmt.where(Object.status.in_(statuses))
        if states:
            stmt = stmt.where(Object.state.in_(states))

        if due_from is not None:
            stmt = stmt.where(Object.due_at >= normalize_tool_datetime(due_from))
        if due_to is not None:
            stmt = stmt.where(Object.due_at <= normalize_tool_datetime(due_to))
        if start_from is not None:
            stmt = stmt.where(Object.start_at >= normalize_tool_datetime(start_from))
        if start_to is not None:
            stmt = stmt.where(Object.start_at <= normalize_tool_datetime(start_to))
        if occurred_from is not None:
            stmt = stmt.where(
                Object.occurred_at >= normalize_tool_datetime(occurred_from)
            )
        if occurred_to is not None:
            stmt = stmt.where(
                Object.occurred_at <= normalize_tool_datetime(occurred_to)
            )

        sort_column = {
            "due_at": Object.due_at,
            "start_at": Object.start_at,
            "occurred_at": Object.occurred_at,
            "created_at": Object.created_at,
            "updated_at": Object.updated_at,
            "title": Object.title,
        }[sort_by]

        if sort_order == "asc":
            primary = nulls_last(sort_column.asc())
        else:
            primary = nulls_last(sort_column.desc())

        stmt = stmt.order_by(primary, Object.created_at.asc(), Object.id.asc())
        stmt = stmt.limit(row_limit)

        return list(self._session.scalars(stmt).all())
