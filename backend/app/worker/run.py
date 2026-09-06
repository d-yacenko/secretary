import logging
import signal
import threading
import time
from collections.abc import Collection

from app.core.config import settings
from app.db.session import SessionLocal
from app.jobs.constants import JOB_TYPE_RUN_SCHEDULED_ACTIVITY, WORKER_IDLE_SLEEP_SECONDS
from app.jobs.worker import process_one_job
from app.services.source_sync_scheduler import SourceSyncScheduler

logger = logging.getLogger(__name__)


def _run_scheduler_maintenance() -> None:
    session = SessionLocal()
    try:
        SourceSyncScheduler(session).run_maintenance()
        from app.ai_audit.trace_service import AITraceService

        AITraceService(session).cleanup_expired()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("source sync scheduler maintenance failed")
    finally:
        session.close()


def _run_job_lane(
    stop: threading.Event,
    *,
    include_types: Collection[str] | None = None,
    exclude_types: Collection[str] | None = None,
    run_scheduler: bool = False,
) -> None:
    last_scheduler_at = 0.0
    while not stop.is_set():
        try:
            if run_scheduler:
                now = time.monotonic()
                if now - last_scheduler_at >= settings.source_sync_scheduler_interval_seconds:
                    _run_scheduler_maintenance()
                    last_scheduler_at = now
            processed = process_one_job(
                include_types=include_types,
                exclude_types=exclude_types,
            )
            if not processed:
                stop.wait(WORKER_IDLE_SLEEP_SECONDS)
        except Exception:
            logger.exception("worker loop error")
            stop.wait(WORKER_IDLE_SLEEP_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("worker started")
    stop = threading.Event()

    def _request_stop(signum: int, _frame: object) -> None:
        logger.info("worker received signal %s", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    scheduled = threading.Thread(
        target=_run_job_lane,
        name="worker-scheduled",
        kwargs={"stop": stop, "include_types": {JOB_TYPE_RUN_SCHEDULED_ACTIVITY}},
        daemon=True,
    )
    general = threading.Thread(
        target=_run_job_lane,
        name="worker-general",
        kwargs={
            "stop": stop,
            "exclude_types": {JOB_TYPE_RUN_SCHEDULED_ACTIVITY},
            "run_scheduler": True,
        },
        daemon=True,
    )
    scheduled.start()
    general.start()
    stop.wait()


if __name__ == "__main__":
    main()
