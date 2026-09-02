import logging

from app.db.session import SessionLocal
from app.jobs.handlers import get_handler
from app.jobs.recurring_job_finalization import (
    finalize_recurring_job_failure,
    finalize_recurring_job_success,
)
from app.llm.embedding_service import EmbeddingService
from app.services.job_queue_service import (
    JobQueueService,
    is_job_error_retryable,
    sanitize_job_error,
)
from app.services.source_sync_preference_service import SourceSyncPreferenceService

logger = logging.getLogger(__name__)


def process_one_job(embedding_service: EmbeddingService | None = None) -> bool:
    session = SessionLocal()
    try:
        queue = JobQueueService(session)
        claimed = queue.claim_next()
        if claimed is None:
            return False
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    handler = get_handler(claimed.type)
    if handler is None:
        session = SessionLocal()
        try:
            JobQueueService(session).mark_failed(claimed.id, "unknown job type")
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to mark unknown job type as failed")
        finally:
            session.close()
        return True

    session = SessionLocal()
    try:
        queue = JobQueueService(session)
        if queue.is_recurring_source_job(claimed.type):
            preferences = SourceSyncPreferenceService.build(session)
            if not preferences.is_job_type_enabled(claimed.user_id, claimed.type):
                job = queue.get_job(claimed.id)
                if job is not None:
                    queue.retire_recurring_source_job(job)
                session.commit()
                return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    try:
        session = SessionLocal()
        try:
            queue = JobQueueService(session)
            handler(session, embedding_service, claimed.payload, claimed.user_id)
            if queue.is_recurring_source_job(claimed.type):
                finalize_recurring_job_success(
                    session,
                    claimed.id,
                    claimed.user_id,
                    claimed.type,
                )
            else:
                queue.mark_done(claimed.id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("job %s (%s) failed: %s", claimed.id, claimed.type, type(exc).__name__)
        session = SessionLocal()
        try:
            queue = JobQueueService(session)
            if queue.is_recurring_source_job(claimed.type):
                finalize_recurring_job_failure(
                    session,
                    claimed.id,
                    claimed.user_id,
                    claimed.type,
                    sanitize_job_error(exc),
                    retryable=is_job_error_retryable(exc),
                )
            else:
                queue.mark_retry(
                    claimed.id,
                    sanitize_job_error(exc),
                    retryable=is_job_error_retryable(exc),
                )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to record job failure for %s", claimed.id)
        finally:
            session.close()

    return True
