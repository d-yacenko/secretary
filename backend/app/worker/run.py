import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SLEEP_SECONDS = 30


def main() -> None:
    logger.info("worker alive")
    while True:
        time.sleep(SLEEP_SECONDS)
        logger.info("worker alive")


if __name__ == "__main__":
    main()
