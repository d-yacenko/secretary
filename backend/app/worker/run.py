import logging
import time

from app.jobs.constants import WORKER_IDLE_SLEEP_SECONDS
from app.jobs.worker import process_one_job
from app.llm.embedding_service import create_embedding_service

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    embedding_service = create_embedding_service()
    logger.info("worker started")
    while True:
        try:
            processed = process_one_job(embedding_service)
            if not processed:
                time.sleep(WORKER_IDLE_SLEEP_SECONDS)
        except Exception:
            logger.exception("worker loop error")
            time.sleep(WORKER_IDLE_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
