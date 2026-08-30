import logging

logger = logging.getLogger(__name__)


def log_transcription_telemetry(
    *,
    model: str,
    input_bytes: int,
    elapsed_ms: int,
    success: bool,
) -> None:
    logger.info(
        "assistant_transcription model=%s input_bytes=%d elapsed_ms=%d success=%s",
        model,
        input_bytes,
        elapsed_ms,
        success,
    )
