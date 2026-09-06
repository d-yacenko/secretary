from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, String, and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import Session

from app.db.models import Object

RECENT_SOURCE_KINDS = frozenset(
    {
        "email",
        "event",
        "calendar_event",
        "chat_message",
        "message",
        "file",
        "document",
        "dataset",
        "folder",
    }
)

RECENT_INTAKE_KINDS = frozenset(
    {
        "note",
        "web_page",
        "file",
        "document",
        "dataset",
        "folder",
    }
)

RECENT_SOURCE_DEFAULT_LIMIT = 30
RECENT_SOURCE_MAX_LIMIT = 50
RECENT_SOURCE_RESERVED_PER_PROVIDER = 3
RECENT_SOURCE_MAX_RESERVED_PROVIDERS = 8
RECENT_SOURCE_EXCERPT_CHARS = 160

GMAIL_NOISE_LABELS = (
    "SPAM",
    "TRASH",
    "CATEGORY_PROMOTIONS",
    "CATEGORY_SOCIAL",
    "CATEGORY_FORUMS",
)

_SOURCE_EVENT_KINDS = ("event", "calendar_event")


def inbox_feed_at(obj: Object) -> datetime:
    if obj.origin == "source":
        if obj.kind in _SOURCE_EVENT_KINDS:
            return obj.start_at or obj.occurred_at or obj.updated_at or obj.created_at
        return obj.occurred_at or obj.updated_at or obj.created_at
    return obj.created_at


def inbox_feed_at_sql() -> ColumnElement[datetime]:
    source_event_at = func.coalesce(
        Object.start_at,
        Object.occurred_at,
        Object.updated_at,
        Object.created_at,
    )
    source_object_at = func.coalesce(
        Object.occurred_at,
        Object.updated_at,
        Object.created_at,
    )
    return case(
        (
            Object.origin == "source",
            case(
                (Object.kind.in_(_SOURCE_EVENT_KINDS), source_event_at),
                else_=source_object_at,
            ),
        ),
        (
            or_(Object.origin == "explicit", Object.origin == "user"),
            Object.created_at,
        ),
        else_=Object.created_at,
    )


class RecentSourceService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    @staticmethod
    def _gmail_feed_eligible_clause() -> object:
        labels = Object.metadata_["labels"]
        noise_any = labels.op("?|")(
            array(GMAIL_NOISE_LABELS, type_=ARRAY(String)),
        )
        return or_(
            Object.provider != "gmail",
            labels.is_(None),
            ~noise_any,
        )

    @staticmethod
    def _not_child_email_attachment_clause() -> object:
        parent_email_id = Object.metadata_["parent_email_id"].as_string()
        return ~and_(
            Object.origin == "source",
            Object.kind == "file",
            parent_email_id.is_not(None),
            parent_email_id != "",
        )

    def _source_feed_clause(self) -> object:
        return and_(
            Object.origin == "source",
            Object.kind.in_(tuple(RECENT_SOURCE_KINDS)),
        )

    def _intake_feed_clause(self) -> object:
        return and_(
            or_(Object.origin == "explicit", Object.origin == "user"),
            Object.kind.in_(tuple(RECENT_INTAKE_KINDS)),
            Object.kind != "task",
        )

    def _eligible_filters(self) -> object:
        return and_(
            Object.user_id == self._user_id,
            or_(self._source_feed_clause(), self._intake_feed_clause()),
            Object.state != "rejected",
            Object.deleted_at.is_(None),
            or_(Object.status.is_(None), Object.status != "deleted"),
            self._gmail_feed_eligible_clause(),
            self._not_child_email_attachment_clause(),
        )

    def list_recent(self, limit: int = RECENT_SOURCE_DEFAULT_LIMIT) -> list[Object]:
        bounded_limit = min(max(limit, 1), RECENT_SOURCE_MAX_LIMIT)
        eligible_filters = self._eligible_filters()
        feed_at = inbox_feed_at_sql()
        feed_order = (feed_at.desc(), Object.id.desc())

        top_provider_rows = self._session.execute(
            select(Object.provider)
            .where(eligible_filters, Object.provider.is_not(None))
            .group_by(Object.provider)
            .order_by(func.max(feed_at).desc(), Object.provider.asc())
            .limit(RECENT_SOURCE_MAX_RESERVED_PROVIDERS)
        ).all()
        selected_providers = [row[0] for row in top_provider_rows]

        reserved_ids: list[UUID] = []
        if selected_providers:
            row_number = func.row_number().over(
                partition_by=Object.provider,
                order_by=feed_order,
            )
            ranked = (
                select(Object.id, row_number.label("row_number"))
                .where(eligible_filters, Object.provider.in_(selected_providers))
                .subquery("recent_source_ranked")
            )
            reserved_id_rows = self._session.execute(
                select(ranked.c.id).where(
                    ranked.c.row_number <= RECENT_SOURCE_RESERVED_PER_PROVIDER
                )
            ).all()
            reserved_ids = [row[0] for row in reserved_id_rows]

        remaining = bounded_limit - len(reserved_ids)
        fill_ids: list[UUID] = []
        if remaining > 0:
            fill_stmt = (
                select(Object.id)
                .where(eligible_filters)
                .order_by(*feed_order)
            )
            if reserved_ids:
                fill_stmt = fill_stmt.where(Object.id.not_in(reserved_ids))
            fill_id_rows = self._session.execute(fill_stmt.limit(remaining)).all()
            fill_ids = [row[0] for row in fill_id_rows]

        all_ids = reserved_ids + fill_ids
        if not all_ids:
            return []

        objects = list(
            self._session.scalars(select(Object).where(Object.id.in_(all_ids)))
        )
        objects.sort(key=lambda obj: (inbox_feed_at(obj), obj.id), reverse=True)
        return objects

    @staticmethod
    def excerpt(body: str | None) -> str | None:
        if not body:
            return None
        normalized = body.replace("\\n", " ").replace("\n", " ")
        text = " ".join(normalized.split())
        if len(text) <= RECENT_SOURCE_EXCERPT_CHARS:
            return text
        return text[:RECENT_SOURCE_EXCERPT_CHARS].rstrip() + "…"
