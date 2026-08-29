from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Notification, Object
from app.notifications.constants import (
    NOTIFICATION_STATUS_NEW,
    NOTIFICATION_STATUS_READ,
)

TODAY_MAX_TASKS = 100
TODAY_MAX_EVENTS = 100
TODAY_MAX_NOTIFICATIONS = 50

TERMINAL_TASK_STATUSES = frozenset({"deleted", "done", "completed", "cancelled"})
IMPORTANT_PRIORITIES = frozenset({"high", "urgent"})


class TodayService:
    def __init__(self, session: Session, user_id) -> None:
        self._session = session
        self._user_id = user_id

    def snapshot(self, reference_at: datetime | None = None) -> dict:
        tz = ZoneInfo(settings.secretary_timezone)
        now_local = (
            reference_at.astimezone(tz)
            if reference_at is not None
            else datetime.now(tz)
        )
        day_start = datetime.combine(now_local.date(), time.min, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        tasks = self._tasks_for_day(day_start, day_end, now_local)
        events = self._events_for_day(day_start, day_end)
        notifications = self._important_notifications()

        return {
            "date": now_local.date().isoformat(),
            "timezone": settings.secretary_timezone,
            "tasks": tasks,
            "calendar_events": events,
            "notifications": notifications,
        }

    def _tasks_for_day(
        self,
        day_start: datetime,
        day_end: datetime,
        now_local: datetime,
    ) -> list[Object]:
        stmt = (
            select(Object)
            .where(
                Object.user_id == self._user_id,
                Object.kind == "task",
                Object.state == "confirmed",
                Object.due_at.is_not(None),
                or_(
                    and_(Object.due_at >= day_start, Object.due_at < day_end),
                    Object.due_at < day_start,
                ),
            )
            .order_by(Object.due_at.asc())
            .limit(TODAY_MAX_TASKS)
        )
        rows = list(self._session.scalars(stmt))
        return [row for row in rows if row.status not in TERMINAL_TASK_STATUSES]

    def _events_for_day(self, day_start: datetime, day_end: datetime) -> list[Object]:
        stmt = (
            select(Object)
            .where(
                Object.user_id == self._user_id,
                Object.kind == "event",
                or_(Object.status.is_(None), Object.status != "deleted"),
                Object.start_at.is_not(None),
                or_(
                    and_(
                        Object.due_at.is_(None),
                        Object.start_at >= day_start,
                        Object.start_at < day_end,
                    ),
                    and_(
                        Object.due_at.is_not(None),
                        Object.start_at < day_end,
                        Object.due_at > day_start,
                    ),
                ),
            )
            .order_by(Object.start_at.asc())
            .limit(TODAY_MAX_EVENTS)
        )
        return list(self._session.scalars(stmt))

    def _important_notifications(self) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == self._user_id,
                Notification.priority.in_(IMPORTANT_PRIORITIES),
                Notification.status.in_((NOTIFICATION_STATUS_NEW, NOTIFICATION_STATUS_READ)),
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(TODAY_MAX_NOTIFICATIONS)
        )
        return list(self._session.scalars(stmt))
