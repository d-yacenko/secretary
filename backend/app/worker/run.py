import logging
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.jobs.constants import WORKER_IDLE_SLEEP_SECONDS
from app.jobs.worker import process_one_job
from app.services.source_sync_scheduler import SourceSyncScheduler

logger = logging.getLogger(__name__)


def _run_scheduler_maintenance() -> None:
    session = SessionLocal()
    try:
        SourceSyncScheduler(session).run_maintenance()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("source sync scheduler maintenance failed")
    finally:
        session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("worker started")
    last_scheduler_at = 0.0
    while True:
        try:
            now = time.monotonic()
            if now - last_scheduler_at >= settings.source_sync_scheduler_interval_seconds:
                _run_scheduler_maintenance()
                last_scheduler_at = now
            processed = process_one_job()
            if not processed:
                time.sleep(WORKER_IDLE_SLEEP_SECONDS)
        except Exception:
            logger.exception("worker loop error")
            time.sleep(WORKER_IDLE_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
