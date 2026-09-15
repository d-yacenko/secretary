from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import InboxReviewMarker, Object
from app.services.errors import NotFoundError, ValidationError
from app.services.inbox_review_snapshot_cursor import (
    canonical_feed_at,
    decode_inbox_review_snapshot_cursor,
    encode_inbox_review_snapshot_cursor,
)
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


@dataclass(frozen=True)
class InboxSinceReviewMarkerPage:
    marker: ReviewMarkerRecord | None
    items: list[Object]
    has_more: bool
    snapshot_top_object_id: UUID | None = None
    snapshot_top_feed_at: datetime | None = None
    total_count: int = 0
    returned_count: int = 0
    remaining_count: int = 0
    next_cursor: str | None = None


@dataclass(frozen=True)
class ReviewMarkerCompletion:
    status: str
    marker: ReviewMarkerRecord | None


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

    def list_inbox_since_review_marker(
        self,
        limit: int,
        cursor: str | None = None,
    ) -> InboxSinceReviewMarkerPage:
        if cursor:
            return self._list_continuation(limit=limit, cursor=cursor)
        marker = self.get_marker()
        if marker is None:
            return InboxSinceReviewMarkerPage(marker=None, items=[], has_more=False)
        page = self._feed.list_review_window(
            anchor_feed_at=marker.anchor_feed_at,
            anchor_object_id=marker.anchor_object_id,
            snapshot_top_feed_at=None,
            snapshot_top_object_id=None,
            after_feed_at=None,
            after_object_id=None,
            limit=limit,
        )
        if not page.items:
            return InboxSinceReviewMarkerPage(
                marker=marker,
                items=[],
                has_more=False,
                total_count=0,
                returned_count=0,
                remaining_count=0,
            )
        snapshot_top = page.items[0]
        snapshot_top_feed_at = inbox_feed_at(snapshot_top)
        total_count = self._feed.count_review_window(
            anchor_feed_at=marker.anchor_feed_at,
            anchor_object_id=marker.anchor_object_id,
            snapshot_top_feed_at=snapshot_top_feed_at,
            snapshot_top_object_id=snapshot_top.id,
        )
        last = page.items[-1]
        remaining_count = self._feed.count_older_in_review_window(
            anchor_feed_at=marker.anchor_feed_at,
            anchor_object_id=marker.anchor_object_id,
            snapshot_top_feed_at=snapshot_top_feed_at,
            snapshot_top_object_id=snapshot_top.id,
            last_feed_at=inbox_feed_at(last),
            last_object_id=last.id,
        )
        next_cursor = None
        if page.has_more:
            next_cursor = encode_inbox_review_snapshot_cursor(
                anchor_object_id=marker.anchor_object_id,
                anchor_feed_at=marker.anchor_feed_at,
                snapshot_top_object_id=snapshot_top.id,
                snapshot_top_feed_at=snapshot_top_feed_at,
                last_object_id=last.id,
                last_feed_at=inbox_feed_at(last),
            )
        return InboxSinceReviewMarkerPage(
            marker=marker,
            items=page.items,
            has_more=page.has_more,
            snapshot_top_object_id=snapshot_top.id,
            snapshot_top_feed_at=snapshot_top_feed_at,
            total_count=total_count,
            returned_count=len(page.items),
            remaining_count=remaining_count,
            next_cursor=next_cursor,
        )

    def complete_review(
        self,
        *,
        expected_anchor_object_id: UUID,
        expected_anchor_feed_at: datetime,
        snapshot_top_object_id: UUID,
        snapshot_top_feed_at: datetime,
    ) -> ReviewMarkerCompletion:
        expected_anchor_feed_at = canonical_feed_at(expected_anchor_feed_at)
        snapshot_top_feed_at = canonical_feed_at(snapshot_top_feed_at)
        current = self.get_marker()
        snapshot_obj = self._feed.get_inbox_eligible(snapshot_top_object_id)
        if snapshot_obj is None:
            return ReviewMarkerCompletion(status="conflict", marker=current)
        if canonical_feed_at(inbox_feed_at(snapshot_obj)) != snapshot_top_feed_at:
            return ReviewMarkerCompletion(status="conflict", marker=current)
        if current is None:
            return ReviewMarkerCompletion(status="conflict", marker=None)
        current_feed_at = canonical_feed_at(current.anchor_feed_at)
        if (
            current.anchor_object_id == expected_anchor_object_id
            and current_feed_at == expected_anchor_feed_at
        ):
            record = self.set_marker(snapshot_top_object_id)
            return ReviewMarkerCompletion(status="advanced", marker=record)
        if not feed_tuple_is_newer(
            snapshot_top_feed_at,
            snapshot_top_object_id,
            current_feed_at,
            current.anchor_object_id,
        ):
            return ReviewMarkerCompletion(status="already_current", marker=current)
        return ReviewMarkerCompletion(status="conflict", marker=current)

    def _list_continuation(self, *, limit: int, cursor: str) -> InboxSinceReviewMarkerPage:
        frozen = decode_inbox_review_snapshot_cursor(cursor)
        frozen_marker = ReviewMarkerRecord(
            anchor_feed_at=frozen.anchor_feed_at,
            anchor_object_id=frozen.anchor_object_id,
            updated_at=frozen.anchor_feed_at,
        )
        page = self._feed.list_review_window(
            anchor_feed_at=frozen.anchor_feed_at,
            anchor_object_id=frozen.anchor_object_id,
            snapshot_top_feed_at=frozen.snapshot_top_feed_at,
            snapshot_top_object_id=frozen.snapshot_top_object_id,
            after_feed_at=frozen.last_feed_at,
            after_object_id=frozen.last_object_id,
            limit=limit,
        )
        total_count = self._feed.count_review_window(
            anchor_feed_at=frozen.anchor_feed_at,
            anchor_object_id=frozen.anchor_object_id,
            snapshot_top_feed_at=frozen.snapshot_top_feed_at,
            snapshot_top_object_id=frozen.snapshot_top_object_id,
        )
        if not page.items:
            return InboxSinceReviewMarkerPage(
                marker=frozen_marker,
                items=[],
                has_more=False,
                snapshot_top_object_id=frozen.snapshot_top_object_id,
                snapshot_top_feed_at=frozen.snapshot_top_feed_at,
                total_count=total_count,
                returned_count=0,
                remaining_count=0,
            )
        last = page.items[-1]
        remaining_count = self._feed.count_older_in_review_window(
            anchor_feed_at=frozen.anchor_feed_at,
            anchor_object_id=frozen.anchor_object_id,
            snapshot_top_feed_at=frozen.snapshot_top_feed_at,
            snapshot_top_object_id=frozen.snapshot_top_object_id,
            last_feed_at=inbox_feed_at(last),
            last_object_id=last.id,
        )
        next_cursor = None
        if page.has_more:
            next_cursor = encode_inbox_review_snapshot_cursor(
                anchor_object_id=frozen.anchor_object_id,
                anchor_feed_at=frozen.anchor_feed_at,
                snapshot_top_object_id=frozen.snapshot_top_object_id,
                snapshot_top_feed_at=frozen.snapshot_top_feed_at,
                last_object_id=last.id,
                last_feed_at=inbox_feed_at(last),
            )
        return InboxSinceReviewMarkerPage(
            marker=frozen_marker,
            items=page.items,
            has_more=page.has_more,
            snapshot_top_object_id=frozen.snapshot_top_object_id,
            snapshot_top_feed_at=frozen.snapshot_top_feed_at,
            total_count=total_count,
            returned_count=len(page.items),
            remaining_count=remaining_count,
            next_cursor=next_cursor,
        )
