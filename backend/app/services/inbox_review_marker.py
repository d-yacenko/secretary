from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import InboxReviewMarker, Object
from app.services.errors import NotFoundError, ValidationError
from app.services.recent_source_service import RecentSourceService, inbox_feed_at


def feed_tuple_is_newer(
    left_feed_at: datetime,
    left_id: UUID,
    right_feed_at: datetime,
    right_id: UUID,
) -> bool:
    """True if left appears above right in canonical Inbox order."""
    if left_feed_at != right_feed_at:
        return left_feed_at > right_feed_at
    return left_id > right_id


def item_is_at_or_above_marker(
    item_feed_at: datetime,
    item_id: UUID,
    anchor_feed_at: datetime,
    anchor_object_id: UUID,
) -> bool:
    """Items at/above the marker are newer than or equal to the persisted anchor tuple."""
    return not feed_tuple_is_newer(
        anchor_feed_at,
        anchor_object_id,
        item_feed_at,
        item_id,
    )


@dataclass(frozen=True)
class ReviewMarkerRecord:
    anchor_feed_at: datetime
    anchor_object_id: UUID
    updated_at: datetime


class InboxReviewMarkerService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._feed = RecentSourceService(session, user_id)

    def get_marker(self) -> ReviewMarkerRecord | None:
        row = self._session.get(InboxReviewMarker, self._user_id)
        if row is None:
            return None
        return ReviewMarkerRecord(
            anchor_feed_at=row.anchor_feed_at,
            anchor_object_id=row.anchor_object_id,
            updated_at=row.updated_at,
        )

    def set_marker(self, after_object_id: UUID) -> ReviewMarkerRecord:
        obj = self._session.scalar(
            select(Object).where(Object.id == after_object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", after_object_id)
        eligible = self._feed.get_inbox_eligible(after_object_id)
        if eligible is None:
            raise ValidationError("object is not eligible for the inbox feed")
        feed_at = inbox_feed_at(eligible)
        stmt = insert(InboxReviewMarker).values(
            user_id=self._user_id,
            anchor_feed_at=feed_at,
            anchor_object_id=eligible.id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[InboxReviewMarker.user_id],
            set_={
                "anchor_feed_at": stmt.excluded.anchor_feed_at,
                "anchor_object_id": stmt.excluded.anchor_object_id,
                "updated_at": func.now(),
            },
        )
        self._session.execute(stmt)
        self._session.flush()
        row = self._session.get(InboxReviewMarker, self._user_id)
        assert row is not None
        self._session.refresh(row)
        return ReviewMarkerRecord(
            anchor_feed_at=row.anchor_feed_at,
            anchor_object_id=row.anchor_object_id,
            updated_at=row.updated_at,
        )

    def clear_marker(self) -> bool:
        row = self._session.get(InboxReviewMarker, self._user_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
