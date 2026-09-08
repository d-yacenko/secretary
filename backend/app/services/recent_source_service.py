from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, String, and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import Session

from app.db.models import Object
from app.services.inbox_feed_cursor import decode_inbox_feed_cursor, encode_inbox_feed_cursor

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
            anchor = obj.start_at or obj.occurred_at or obj.created_at
            return min(anchor, obj.created_at)
        return obj.occurred_at or obj.created_at
    return obj.created_at


def inbox_feed_at_sql() -> ColumnElement[datetime]:
    calendar_anchor = func.coalesce(
        Object.start_at,
        Object.occurred_at,
        Object.created_at,
    )
    source_event_at = func.least(calendar_anchor, Object.created_at)
    source_object_at = func.coalesce(
        Object.occurred_at,
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


@dataclass(frozen=True)
class InboxFeedPage:
    items: list[Object]
    next_cursor: str | None
    has_more: bool


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

    def list_page(
        self,
        limit: int = RECENT_SOURCE_DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> InboxFeedPage:
        bounded_limit = min(max(limit, 1), RECENT_SOURCE_MAX_LIMIT)
        feed_at = inbox_feed_at_sql()
        stmt = (
            select(Object)
            .where(self._eligible_filters())
            .order_by(feed_at.desc(), Object.id.desc())
        )
        if cursor is not None:
            cursor_feed_at, cursor_id = decode_inbox_feed_cursor(cursor)
            stmt = stmt.where(
                or_(
                    feed_at < cursor_feed_at,
                    and_(feed_at == cursor_feed_at, Object.id < cursor_id),
                )
            )
        rows = list(self._session.scalars(stmt.limit(bounded_limit + 1)))
        has_more = len(rows) > bounded_limit
        items = rows[:bounded_limit]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_inbox_feed_cursor(inbox_feed_at(last), last.id)
        return InboxFeedPage(items=items, next_cursor=next_cursor, has_more=has_more)

    def list_recent(self, limit: int = RECENT_SOURCE_DEFAULT_LIMIT) -> list[Object]:
        return self.list_page(limit=limit).items

    @staticmethod
    def excerpt(body: str | None) -> str | None:
        if not body:
            return None
        normalized = body.replace("\\n", " ").replace("\n", " ")
        text = " ".join(normalized.split())
        if len(text) <= RECENT_SOURCE_EXCERPT_CHARS:
            return text
        return text[:RECENT_SOURCE_EXCERPT_CHARS].rstrip() + "…"
