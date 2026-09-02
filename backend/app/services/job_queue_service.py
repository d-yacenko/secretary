from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.connectors.google.api_errors import format_google_api_error
from app.connectors.google.errors import GoogleApiError, GoogleConnectorError
from app.connectors.yandex.caldav_api_errors import format_yandex_caldav_error
from app.connectors.yandex.errors import (
    YandexCalDavError,
    YandexConnectorError,
    YandexImapError,
)
from app.db.models import Job
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_INGEST_LOCAL_FILE,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
    JOB_TYPE_SYNC_MATTERMOST,
    JOB_TYPE_SYNC_YANDEX_CALENDAR,
    JOB_TYPE_SYNC_YANDEX_MAIL,
    MAX_JOB_ATTEMPTS,
    MAX_LAST_ERROR_LENGTH,
    RECURRING_SOURCE_JOB_TYPES,
    RETRY_BACKOFF_SECONDS,
    STALE_LOCK_MINUTES,
)
from app.services.background_ai_errors import BackgroundAIConfigurationError
from app.services.user_openai_credential_errors import UserOpenAICredentialConfigurationError


def utcnow() -> datetime:
    return datetime.now(UTC)


def sanitize_job_error(exc: BaseException) -> str:
    if isinstance(exc, GoogleApiError):
        return format_google_api_error(exc)
    if isinstance(exc, YandexCalDavError):
        return format_yandex_caldav_error(exc)
    message = str(exc).strip() or type(exc).__name__
    first_line = message.splitlines()[0]
    lowered = first_line.lower()
    sensitive_needles = (
        "bearer ",
        "authorization:",
        "authorization ",
        "access_token",
        "refresh_token",
        "access-token",
        "personal-access",
        "personal access",
        "encrypted",
        "sk-",
    )
    for needle in sensitive_needles:
        if needle in lowered:
            return type(exc).__name__
    return first_line[:MAX_LAST_ERROR_LENGTH]


def is_job_error_retryable(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (UserOpenAICredentialConfigurationError, BackgroundAIConfigurationError),
    ):
        return False
    if isinstance(exc, GoogleApiError):
        return exc.retryable
    if isinstance(exc, YandexCalDavError):
        return exc.retryable
    if isinstance(exc, YandexImapError):
        return True
    if isinstance(exc, YandexConnectorError):
        return exc.retryable
    if isinstance(exc, GoogleConnectorError):
        return exc.retryable
    return True


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
            self._apply_recurring_failure_cooldown(job)
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
        self._apply_recurring_failure_cooldown(job)

    def mark_retry(self, job_id: UUID, error: str, *, retryable: bool = True) -> None:
        job = self._require_job(job_id)
        job.last_error = error[:MAX_LAST_ERROR_LENGTH]
        job.updated_at = utcnow()
        if not retryable and job.type in RECURRING_SOURCE_JOB_TYPES:
            job.status = JOB_STATUS_PENDING
            job.attempts = 0
            job.locked_at = None
            self._apply_recurring_failure_cooldown(job)
            return
        if job.attempts >= MAX_JOB_ATTEMPTS:
            job.status = JOB_STATUS_FAILED
            job.locked_at = None
            self._apply_recurring_failure_cooldown(job)
            return

        backoff = RETRY_BACKOFF_SECONDS.get(job.attempts, RETRY_BACKOFF_SECONDS[2])
        job.status = JOB_STATUS_PENDING
        job.locked_at = None
        job.run_after = utcnow() + timedelta(seconds=backoff)

    def find_recurring_source_job(
        self,
        user_id: UUID,
        job_type: str,
        account_id: UUID,
    ) -> Job | None:
        account_key = str(account_id)
        return self._session.scalar(
            select(Job).where(
                Job.user_id == user_id,
                Job.type == job_type,
                Job.payload["account_id"].as_string() == account_key,
                Job.status.in_(
                    (JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_FAILED)
                ),
            )
        )

    def ensure_recurring_source_job(
        self,
        job_type: str,
        account_id: UUID,
        user_id: UUID,
        run_after: datetime | None = None,
    ) -> Job:
        existing = self.find_recurring_source_job(user_id, job_type, account_id)
        now = utcnow()
        if existing is not None:
            return existing
        return self.enqueue(
            job_type,
            {"account_id": str(account_id)},
            user_id,
            run_after=run_after or now,
        )

    def retire_recurring_source_job(self, job: Job) -> None:
        job.status = JOB_STATUS_DONE
        job.locked_at = None
        job.last_error = None
        job.updated_at = utcnow()
        self._session.flush()

    def trigger_recurring_source_job(
        self,
        user_id: UUID,
        job_type: str,
        account_id: UUID,
    ) -> bool:
        job = self.find_recurring_source_job(user_id, job_type, account_id)
        if job is None:
            return False
        now = utcnow()
        job.run_after = now
        if job.status == JOB_STATUS_FAILED:
            job.status = JOB_STATUS_PENDING
            job.attempts = 0
        job.updated_at = now
        self._session.flush()
        return True

    def rearm_failed_recurring_job(
        self,
        job: Job,
        cooldown_seconds: int,
    ) -> bool:
        if job.status != JOB_STATUS_FAILED:
            return False
        now = utcnow()
        if job.run_after > now:
            return False
        job.status = JOB_STATUS_PENDING
        job.attempts = 0
        job.last_error = None
        job.run_after = now
        job.updated_at = now
        self._session.flush()
        return True

    def mark_recurring_success(self, job_id: UUID, interval_seconds: int) -> None:
        job = self._require_job(job_id)
        now = utcnow()
        payload = dict(job.payload or {})
        payload["last_success_at"] = now.isoformat()
        job.payload = payload
        job.status = JOB_STATUS_PENDING
        job.attempts = 0
        job.last_error = None
        job.locked_at = None
        job.run_after = now + timedelta(seconds=interval_seconds)
        job.updated_at = now

    def recurring_interval_seconds(self, job_type: str) -> int:
        from app.core.config import settings

        mapping = {
            JOB_TYPE_SYNC_GOOGLE_GMAIL: settings.source_sync_gmail_interval_seconds,
            JOB_TYPE_SYNC_YANDEX_MAIL: settings.source_sync_yandex_mail_interval_seconds,
            JOB_TYPE_SYNC_GOOGLE_CALENDAR: settings.source_sync_google_calendar_interval_seconds,
            JOB_TYPE_SYNC_YANDEX_CALENDAR: settings.source_sync_yandex_calendar_interval_seconds,
            JOB_TYPE_SYNC_MATTERMOST: settings.source_sync_mattermost_interval_seconds,
        }
        return mapping.get(job_type, settings.source_sync_gmail_interval_seconds)

    def is_recurring_source_job(self, job_type: str) -> bool:
        return job_type in RECURRING_SOURCE_JOB_TYPES

    def _apply_recurring_failure_cooldown(self, job: Job) -> None:
        if job.type not in RECURRING_SOURCE_JOB_TYPES:
            return
        from app.core.config import settings

        job.run_after = utcnow() + timedelta(
            seconds=settings.source_sync_failed_rearm_seconds
        )

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
