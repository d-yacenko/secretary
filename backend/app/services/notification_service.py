from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Notification
from app.notifications.constants import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    NOTIFICATION_PRIORITIES,
    NOTIFICATION_STATUS_ACCEPTED,
    NOTIFICATION_STATUS_IGNORED,
    NOTIFICATION_STATUS_NEW,
    NOTIFICATION_STATUS_READ,
    NOTIFICATION_STATUS_RESOLVED,
    NOTIFICATION_STATUSES,
)
from app.services.errors import NotFoundError, ValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        title: str,
        body: str | None,
        priority: str,
        proposal: dict,
        source_object_id: UUID | None = None,
        related_object_id: UUID | None = None,
    ) -> Notification:
        if priority not in NOTIFICATION_PRIORITIES:
            raise ValidationError(f"invalid notification priority: {priority}")
        notification = Notification(
            title=title,
            body=body,
            priority=priority,
            status=NOTIFICATION_STATUS_NEW,
            source_object_id=source_object_id,
            related_object_id=related_object_id,
            proposal_=proposal,
        )
        self._session.add(notification)
        self._session.flush()
        return notification

    def get(self, notification_id: UUID) -> Notification:
        notification = self._session.get(Notification, notification_id)
        if notification is None:
            raise NotFoundError("notification", notification_id)
        return notification

    def list_notifications(
        self,
        status: str | None = None,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[Notification]:
        if status is not None and status not in NOTIFICATION_STATUSES:
            raise ValidationError(f"invalid notification status: {status}")
        bounded_limit = max(1, min(limit, MAX_LIST_LIMIT))
        stmt = select(Notification).order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        if status is not None:
            stmt = stmt.where(Notification.status == status)
        stmt = stmt.limit(bounded_limit)
        return list(self._session.scalars(stmt))

    def mark_read(self, notification_id: UUID) -> Notification:
        notification = self.get(notification_id)
        if notification.status == NOTIFICATION_STATUS_NEW:
            notification.status = NOTIFICATION_STATUS_READ
        if notification.read_at is None:
            notification.read_at = utcnow()
        notification.updated_at = utcnow()
        self._session.flush()
        return notification

    def accept(self, notification_id: UUID) -> Notification:
        notification = self.get(notification_id)
        notification.status = NOTIFICATION_STATUS_ACCEPTED
        if notification.read_at is None:
            notification.read_at = utcnow()
        notification.updated_at = utcnow()
        self._session.flush()
        return notification

    def ignore(self, notification_id: UUID) -> Notification:
        notification = self.get(notification_id)
        notification.status = NOTIFICATION_STATUS_IGNORED
        if notification.read_at is None:
            notification.read_at = utcnow()
        notification.updated_at = utcnow()
        self._session.flush()
        return notification

    def resolve(self, notification_id: UUID) -> Notification:
        notification = self.get(notification_id)
        notification.status = NOTIFICATION_STATUS_RESOLVED
        if notification.read_at is None:
            notification.read_at = utcnow()
        notification.updated_at = utcnow()
        self._session.flush()
        return notification
