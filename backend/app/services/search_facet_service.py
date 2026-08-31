from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Object
from app.domain.task_lifecycle import TASK_STATUS_DELETED
from app.services.provenance import REJECTED_STATE


class SearchFacetService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def _visibility_filter(self):
        return (
            Object.user_id == self._user_id,
            Object.state != REJECTED_STATE,
            or_(
                Object.kind != "task",
                Object.status.is_(None),
                Object.status != TASK_STATUS_DELETED,
            ),
        )

    def facets(self) -> dict[str, list[dict[str, object]]]:
        base = self._visibility_filter()
        kind_rows = self._session.execute(
            select(Object.kind, func.count())
            .where(*base)
            .group_by(Object.kind)
            .order_by(Object.kind.asc())
        ).all()
        provider_rows = self._session.execute(
            select(Object.provider, func.count())
            .where(*base, Object.provider.is_not(None))
            .group_by(Object.provider)
            .order_by(Object.provider.asc())
        ).all()
        return {
            "kinds": [
                {"value": kind, "count": int(count)} for kind, count in kind_rows
            ],
            "providers": [
                {"value": provider, "count": int(count)}
                for provider, count in provider_rows
            ],
        }
