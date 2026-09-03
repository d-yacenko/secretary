import time

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.ai_audit.context import get_active_trace
from app.ai_audit.instrumentation import record_simple_model_call
from app.assistant.transcription_audio import read_bounded_transcription_audio
from app.assistant.transcription_telemetry import log_transcription_telemetry
from app.core.config import settings
from app.llm.fake_transcription_provider import FakeTranscriptionProvider
from app.llm.openai_transcription_provider import (
    OpenAITranscriptionProvider,
    TranscriptionProviderError,
)


class TranscriptionConfigurationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TranscriptionProvider:
    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None,
    ) -> str:
        raise NotImplementedError


async def transcribe_audio_upload(
    upload: UploadFile,
    provider: TranscriptionProvider,
) -> str:
    audio_bytes, filename = await read_bounded_transcription_audio(upload)
    model = _provider_model(provider)
    started = time.perf_counter()
    try:
        text = await run_in_threadpool(
            provider.transcribe,
            audio_bytes,
            filename,
            upload.content_type,
        )
    except TranscriptionProviderError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_transcription_telemetry(
            model=model,
            input_bytes=len(audio_bytes),
            elapsed_ms=elapsed_ms,
            success=False,
        )
        raise

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if get_active_trace() is not None:
        record_simple_model_call(
            model=model,
            input_chars=len(audio_bytes),
            output_chars=len(text),
            elapsed_ms=elapsed_ms,
            extra={"audio_bytes": len(audio_bytes)},
        )
    log_transcription_telemetry(
        model=model,
        input_bytes=len(audio_bytes),
        elapsed_ms=elapsed_ms,
        success=True,
    )
    return text


def _provider_model(provider: TranscriptionProvider) -> str:
    model = getattr(provider, "model", None)
    if isinstance(model, str) and model:
        return model
    return settings.openai_transcription_model.strip() or "unknown"


def create_transcription_provider_for_api_key(
    api_key: str | None,
) -> OpenAITranscriptionProvider:
    if not api_key:
        raise TranscriptionConfigurationError("OpenAI API key is not configured")
    model = settings.openai_transcription_model.strip()
    if not model:
        raise TranscriptionConfigurationError("OPENAI_TRANSCRIPTION_MODEL cannot be blank")
    return OpenAITranscriptionProvider(api_key=api_key, model=model)


def create_transcription_provider() -> OpenAITranscriptionProvider:
    deployment_key = settings.openai_api_key.strip() or None
    return create_transcription_provider_for_api_key(deployment_key)


def create_fake_transcription_provider(text: str = "recognized speech") -> FakeTranscriptionProvider:
    return FakeTranscriptionProvider(text=text)
