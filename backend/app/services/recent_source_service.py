from uuid import UUID

from sqlalchemy import String, and_, func, or_, select
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
            or_(Object.status.is_(None), Object.status != "deleted"),
            self._gmail_feed_eligible_clause(),
        )

    def list_recent(self, limit: int = RECENT_SOURCE_DEFAULT_LIMIT) -> list[Object]:
        bounded_limit = min(max(limit, 1), RECENT_SOURCE_MAX_LIMIT)
        eligible_filters = self._eligible_filters()

        top_provider_rows = self._session.execute(
            select(Object.provider)
            .where(eligible_filters, Object.provider.is_not(None))
            .group_by(Object.provider)
            .order_by(func.max(Object.created_at).desc(), Object.provider.asc())
            .limit(RECENT_SOURCE_MAX_RESERVED_PROVIDERS)
        ).all()
        selected_providers = [row[0] for row in top_provider_rows]

        reserved_ids: list[UUID] = []
        if selected_providers:
            row_number = func.row_number().over(
                partition_by=Object.provider,
                order_by=(Object.created_at.desc(), Object.id.desc()),
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
                .order_by(Object.created_at.desc(), Object.id.desc())
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
        objects.sort(key=lambda obj: (obj.created_at, obj.id), reverse=True)
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
