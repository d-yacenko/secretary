import logging

from app.db.session import SessionLocal
from app.jobs.handlers import get_handler
from app.llm.embedding_service import EmbeddingService
from app.services.job_queue_service import sanitize_job_error
from app.services.job_queue_service import JobQueueService

logger = logging.getLogger(__name__)


def process_one_job(embedding_service: EmbeddingService) -> bool:
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

    try:
        session = SessionLocal()
        try:
            handler(session, embedding_service, claimed.payload, claimed.user_id)
            JobQueueService(session).mark_done(claimed.id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:
        logger.warning("job %s (%s) failed: %s", claimed.id, claimed.type, type(exc).__name__)
        session = SessionLocal()
        try:
            JobQueueService(session).mark_retry(claimed.id, sanitize_job_error(exc))
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to record job failure for %s", claimed.id)
        finally:
            session.close()

    return True
