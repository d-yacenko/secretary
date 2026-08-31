from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.schemas import InboxOut, InboxSourceObjectOut, NotificationOut, SourceSyncStatusOut
from app.core.current_user import CurrentUserContext
from app.notifications.constants import NOTIFICATION_FILTER_UNRESOLVED
from app.services.notification_service import NotificationService
from app.services.object_primary_date import object_primary_search_datetime
from app.services.recent_source_service import RecentSourceService
from app.services.source_status_service import SourceStatusService

router = APIRouter(tags=["inbox"])


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
    recent_objects = RecentSourceService(session, user_id).list_recent(limit=recent_limit)
    status_rows = SourceStatusService(session, user_id).list_status()
    return InboxOut(
        unresolved_notifications=[
            NotificationOut.from_model(notification) for notification in notifications
        ],
        recent_source_objects=[
            InboxSourceObjectOut(
                id=obj.id,
                title=obj.title,
                kind=obj.kind,
                provider=obj.provider,
                state=obj.state,
                status=obj.status,
                primary_at=object_primary_search_datetime(obj),
                excerpt=RecentSourceService.excerpt(obj.body),
            )
            for obj in recent_objects
        ],
        source_sync_status=[
            SourceSyncStatusOut(
                source=row.source,
                provider=row.provider,
                account_id=row.account_id,
                account_label=row.account_label,
                status=row.status,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                next_sync_at=row.next_sync_at,
                last_error=row.last_error,
            )
            for row in status_rows
        ],
    )
