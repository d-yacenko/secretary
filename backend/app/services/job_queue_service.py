from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Job
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_INGEST_LOCAL_FILE,
    MAX_JOB_ATTEMPTS,
    MAX_LAST_ERROR_LENGTH,
    RETRY_BACKOFF_SECONDS,
    STALE_LOCK_MINUTES,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_job_error(exc: BaseException) -> str:
    message = str(exc).strip() or type(exc).__name__
    first_line = message.splitlines()[0]
    return first_line[:MAX_LAST_ERROR_LENGTH]


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    type: str
    payload: dict
    attempts: int
    user_id: UUID


class JobQueueService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        job_type: str,
        payload: dict,
        user_id: UUID,
        run_after: datetime | None = None,
    ) -> Job:
        job = Job(
            user_id=user_id,
            type=job_type,
            payload=payload,
            status=JOB_STATUS_PENDING,
            attempts=0,
            run_after=run_after or utcnow(),
        )
        self._session.add(job)
        self._session.flush()
        return job

    def claim_next(self) -> ClaimedJob | None:
        now = utcnow()
        stale_threshold = now - timedelta(minutes=STALE_LOCK_MINUTES)
        stmt = (
            select(Job)
            .where(
                or_(
                    and_(Job.status == JOB_STATUS_PENDING, Job.run_after <= now),
                    and_(
                        Job.status == JOB_STATUS_RUNNING,
                        Job.locked_at.is_not(None),
                        Job.locked_at < stale_threshold,
                    ),
                )
            )
            .order_by(Job.run_after, Job.created_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = self._session.scalar(stmt)
        if job is None:
            return None

        if (
            job.status == JOB_STATUS_RUNNING
            and job.attempts >= MAX_JOB_ATTEMPTS
        ):
            job.status = JOB_STATUS_FAILED
            job.last_error = (job.last_error or "stale lock exceeded max attempts")[
                :MAX_LAST_ERROR_LENGTH
            ]
            job.locked_at = None
            job.updated_at = now
            self._session.flush()
            return None

        job.status = JOB_STATUS_RUNNING
        job.attempts += 1
        job.locked_at = now
        job.updated_at = now
        self._session.flush()
        return ClaimedJob(
            id=job.id,
            type=job.type,
            payload=dict(job.payload),
            attempts=job.attempts,
            user_id=job.user_id,
        )

    def mark_done(self, job_id: UUID) -> None:
        job = self._require_job(job_id)
        job.status = JOB_STATUS_DONE
        job.locked_at = None
        job.updated_at = utcnow()

    def mark_failed(self, job_id: UUID, error: str) -> None:
        job = self._require_job(job_id)
        job.status = JOB_STATUS_FAILED
        job.last_error = error[:MAX_LAST_ERROR_LENGTH]
        job.locked_at = None
        job.updated_at = utcnow()

    def mark_retry(self, job_id: UUID, error: str) -> None:
        job = self._require_job(job_id)
        job.last_error = error[:MAX_LAST_ERROR_LENGTH]
        job.updated_at = utcnow()
        if job.attempts >= MAX_JOB_ATTEMPTS:
            job.status = JOB_STATUS_FAILED
            job.locked_at = None
            return

        backoff = RETRY_BACKOFF_SECONDS.get(job.attempts, RETRY_BACKOFF_SECONDS[2])
        job.status = JOB_STATUS_PENDING
        job.locked_at = None
        job.run_after = utcnow() + timedelta(seconds=backoff)

    def get_job(self, job_id: UUID) -> Job | None:
        return self._session.get(Job, job_id)

    def has_pending_ingest_job(
        self,
        object_id: UUID,
        expected_revision: str | None,
        expected_policy: str | None,
        user_id: UUID,
    ) -> bool:
        jobs = self._session.scalars(
            select(Job).where(
                Job.user_id == user_id,
                Job.type == JOB_TYPE_INGEST_LOCAL_FILE,
                Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING)),
            )
        )
        object_key = str(object_id)
        for job in jobs:
            payload = job.payload or {}
            if payload.get("object_id") != object_key:
                continue
            if payload.get("expected_revision") != expected_revision:
                continue
            if payload.get("expected_policy") != expected_policy:
                continue
            return True
        return False

    def _require_job(self, job_id: UUID) -> Job:
        job = self._session.get(Job, job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        return job
