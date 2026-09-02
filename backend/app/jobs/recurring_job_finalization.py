from uuid import UUID

from sqlalchemy.orm import Session

from app.services.job_queue_service import JobQueueService
from app.services.source_sync_preference_service import SourceSyncPreferenceService


def finalize_recurring_job_success(
    session: Session,
    job_id: UUID,
    user_id: UUID,
    job_type: str,
) -> None:
    queue = JobQueueService(session)
    preferences = SourceSyncPreferenceService.build(session)
    job = queue.get_job(job_id)
    if job is None:
        return
    if not preferences.is_job_type_enabled(user_id, job_type):
        queue.retire_recurring_source_job(job)
        return
    interval = preferences.effective_interval_seconds_for_job_type(user_id, job_type)
    queue.mark_recurring_success(job_id, interval)


def finalize_recurring_job_failure(
    session: Session,
    job_id: UUID,
    user_id: UUID,
    job_type: str,
    error: str,
    *,
    retryable: bool,
) -> None:
    queue = JobQueueService(session)
    preferences = SourceSyncPreferenceService.build(session)
    job = queue.get_job(job_id)
    if job is None:
        return
    if not preferences.is_job_type_enabled(user_id, job_type):
        queue.retire_recurring_source_job(job)
        return
    queue.mark_retry(job_id, error, retryable=retryable)
