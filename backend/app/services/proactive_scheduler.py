from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, UserSettings
from app.jobs.constants import (
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_PROACTIVE_REVIEW,
    RECURRING_FAILED_REARM_SECONDS,
)
from app.proactive.constants import (
    PROACTIVE_INTERVAL_MINUTES_DEFAULT,
    PROACTIVE_INTERVAL_MINUTES_MAX,
    PROACTIVE_INTERVAL_MINUTES_MIN,
)
from app.services.effective_user_settings_service import EffectiveUserSettingsService
from app.services.job_queue_service import JobQueueService, utcnow

_ACTIVE_STATUSES = (JOB_STATUS_PENDING, JOB_STATUS_RUNNING)
_HELD_STATUSES = (JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_FAILED)


class ProactiveScheduler:
    """Ensure at most one held proactive_review job per opted-in user."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._queue = JobQueueService(session)
        self._settings = EffectiveUserSettingsService.build(session)

    def run_maintenance(self) -> None:
        enabled_user_ids = set(
            self._session.scalars(
                select(UserSettings.user_id).where(UserSettings.proactive_enabled.is_(True))
            )
        )
        for user_id in enabled_user_ids:
            self.sync_user(user_id)
        held_jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.type == JOB_TYPE_PROACTIVE_REVIEW,
                    Job.status.in_(_HELD_STATUSES),
                )
            )
        )
        seen_disabled: set[UUID] = set()
        for job in held_jobs:
            if job.user_id in enabled_user_ids:
                continue
            if job.user_id in seen_disabled:
                if job.status != JOB_STATUS_RUNNING:
                    self._queue.retire_recurring_source_job(job)
                continue
            seen_disabled.add(job.user_id)
            self.sync_user(job.user_id)
        self._rearm_failed_jobs(enabled_user_ids)

    def sync_user(self, user_id: UUID) -> None:
        effective = self._settings.get_settings_view(user_id)
        jobs = self._held_jobs(user_id)
        if not effective.proactive_enabled:
            for job in jobs:
                if job.status != JOB_STATUS_RUNNING:
                    self._queue.retire_recurring_source_job(job)
            return
        active = [job for job in jobs if job.status in _ACTIVE_STATUSES]
        failed = [job for job in jobs if job.status == JOB_STATUS_FAILED]
        if len(active) > 1:
            keep = min(active, key=lambda job: (job.created_at, job.id))
            for job in active:
                if job.id != keep.id and job.status != JOB_STATUS_RUNNING:
                    self._queue.retire_recurring_source_job(job)
            return
        if active:
            return
        if failed:
            return
        now = utcnow()
        interval = self._bounded_interval(effective.proactive_interval_minutes)
        window_start = now - timedelta(minutes=interval)
        self._queue.enqueue(
            JOB_TYPE_PROACTIVE_REVIEW,
            {"window_start": window_start.isoformat()},
            user_id,
            run_after=now,
        )

    def _rearm_failed_jobs(self, enabled_user_ids: set[UUID]) -> None:
        now = utcnow()
        failed_jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.type == JOB_TYPE_PROACTIVE_REVIEW,
                    Job.status == JOB_STATUS_FAILED,
                    Job.run_after <= now,
                )
            )
        )
        for job in failed_jobs:
            if job.user_id not in enabled_user_ids:
                continue
            self._queue.rearm_failed_recurring_job(job, RECURRING_FAILED_REARM_SECONDS)

    def _held_jobs(self, user_id: UUID) -> list[Job]:
        return list(
            self._session.scalars(
                select(Job).where(
                    Job.user_id == user_id,
                    Job.type == JOB_TYPE_PROACTIVE_REVIEW,
                    Job.status.in_(_HELD_STATUSES),
                )
            )
        )

    @staticmethod
    def _bounded_interval(value: int) -> int:
        if value < PROACTIVE_INTERVAL_MINUTES_MIN or value > PROACTIVE_INTERVAL_MINUTES_MAX:
            return PROACTIVE_INTERVAL_MINUTES_DEFAULT
        return value
