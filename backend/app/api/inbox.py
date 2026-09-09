from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.schemas import (
    InboxFeedOut,
    InboxOut,
    InboxReviewMarkerOut,
    InboxSourceObjectOut,
    NotificationOut,
    SourceSyncStatusOut,
)
from app.core.current_user import CurrentUserContext
from app.db.models import Object
from app.notifications.constants import NOTIFICATION_FILTER_UNRESOLVED
from app.services.errors import NotFoundError, ValidationError
from app.services.inbox_review_marker import InboxReviewMarkerService, ReviewMarkerRecord
from app.services.notification_service import NotificationService
from app.services.object_primary_date import object_primary_search_datetime
from app.services.recent_source_service import RecentSourceService, inbox_feed_at
from app.services.source_status_service import SourceStatusService

router = APIRouter(tags=["inbox"])


class ReviewMarkerPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    after_object_id: UUID


def _marker_out(record: ReviewMarkerRecord) -> InboxReviewMarkerOut:
    return InboxReviewMarkerOut(
        anchor_feed_at=record.anchor_feed_at,
        anchor_object_id=record.anchor_object_id,
        updated_at=record.updated_at,
    )


def _raise_marker_domain(exc: Exception) -> NoReturn:
    if isinstance(exc, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{exc.resource} not found"
        ) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc
    raise exc


def _source_out(obj: Object) -> InboxSourceObjectOut:
    return InboxSourceObjectOut(
        id=obj.id,
        title=obj.title,
        kind=obj.kind,
        provider=obj.provider,
        origin=obj.origin,
        state=obj.state,
        status=obj.status,
        primary_at=object_primary_search_datetime(obj),
        feed_at=inbox_feed_at(obj),
        excerpt=RecentSourceService.excerpt(obj.body),
    )


@router.get("/inbox", response_model=InboxOut)
def get_inbox(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
    recent_limit: int = Query(default=30, ge=1, le=50),
) -> InboxOut:
    user_id = current_user.user_id
    notifications = NotificationService(session, user_id).list_notifications(
        status=NOTIFICATION_FILTER_UNRESOLVED,
        limit=50,
    )
    page = RecentSourceService(session, user_id).list_page(limit=recent_limit)
    status_rows = SourceStatusService(session, user_id).list_status()
    marker = InboxReviewMarkerService(session, user_id).get_marker()
    return InboxOut(
        unresolved_notifications=[
            NotificationOut.from_model(notification) for notification in notifications
        ],
        recent_source_objects=[_source_out(obj) for obj in page.items],
        source_sync_status=[
            SourceSyncStatusOut(
                source=row.source,
                provider=row.provider,
                account_id=row.account_id,
                account_label=row.account_label,
                enabled=row.enabled,
                status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                next_sync_at=row.next_sync_at,
                last_error=row.last_error,
            )
            for row in status_rows
        ],
        recent_next_cursor=page.next_cursor,
        recent_has_more=page.has_more,
        review_marker=_marker_out(marker) if marker is not None else None,
    )


@router.get("/inbox/feed", response_model=InboxFeedOut)
def get_inbox_feed(
    cursor: str = Query(..., min_length=1),
    limit: int = Query(default=30, ge=1, le=50),
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> InboxFeedOut:
    try:
        page = RecentSourceService(session, current_user.user_id).list_page(
            limit=limit,
            cursor=cursor,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    return InboxFeedOut(
        items=[_source_out(obj) for obj in page.items],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.put("/inbox/review-marker", response_model=InboxReviewMarkerOut)
def put_inbox_review_marker(
    payload: ReviewMarkerPutRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> InboxReviewMarkerOut:
    try:
        record = InboxReviewMarkerService(session, current_user.user_id).set_marker(
            payload.after_object_id
        )
    except (NotFoundError, ValidationError) as exc:
        _raise_marker_domain(exc)
    return _marker_out(record)


@router.delete("/inbox/review-marker")
def delete_inbox_review_marker(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> dict[str, bool]:
    changed = InboxReviewMarkerService(session, current_user.user_id).clear_marker()
    return {"cleared": changed}
