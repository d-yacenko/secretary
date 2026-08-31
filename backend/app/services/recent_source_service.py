from uuid import UUID

from sqlalchemy import or_, select
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
    }
)

RECENT_SOURCE_DEFAULT_LIMIT = 30
RECENT_SOURCE_MAX_LIMIT = 50
RECENT_SOURCE_EXCERPT_CHARS = 160


class RecentSourceService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def list_recent(self, limit: int = RECENT_SOURCE_DEFAULT_LIMIT) -> list[Object]:
        bounded_limit = min(max(limit, 1), RECENT_SOURCE_MAX_LIMIT)
        stmt = (
            select(Object)
            .where(
                Object.user_id == self._user_id,
                Object.origin == "source",
                Object.state != "rejected",
                or_(Object.status.is_(None), Object.status != "deleted"),
                Object.kind.in_(tuple(RECENT_SOURCE_KINDS)),
            )
            .order_by(Object.updated_at.desc(), Object.id.desc())
            .limit(bounded_limit)
        )
        return list(self._session.scalars(stmt))

    @staticmethod
    def excerpt(body: str | None) -> str | None:
        if not body:
            return None
        normalized = body.replace("\\n", " ").replace("\n", " ")
        text = " ".join(normalized.split())
        if len(text) <= RECENT_SOURCE_EXCERPT_CHARS:
            return text
        return text[:RECENT_SOURCE_EXCERPT_CHARS].rstrip() + "…"
