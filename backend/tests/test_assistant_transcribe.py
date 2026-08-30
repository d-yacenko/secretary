"""PHASE 23A — bounded voice transcription endpoint."""

import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.assistant import get_transcription_provider
from app.api.deps import get_db, get_embedding_service
from app.assistant.transcription_constants import MAX_TRANSCRIPTION_AUDIO_BYTES
from app.db.models import Edge, Job, Object
from app.llm.fake_transcription_provider import FakeTranscriptionProvider
from app.llm.openai_transcription_provider import (
    OpenAITranscriptionProvider,
    TranscriptionProviderError,
)
from app.main import app
from app.services.transcription_service import create_fake_transcription_provider


@pytest.fixture
def fake_transcription_provider() -> FakeTranscriptionProvider:
    return create_fake_transcription_provider()


@pytest.fixture
def transcribe_client(
    db_session,
    fake_embedding_service,
    auth_headers,
    fake_transcription_provider,
):
    from tests.conftest import AuthTestClient

    def override_get_db():
        yield db_session

    def override_provider():
        return fake_transcription_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    app.dependency_overrides[get_transcription_provider] = override_provider
    with TestClient(app) as test_client:
        yield AuthTestClient(test_client, auth_headers), fake_transcription_provider
    app.dependency_overrides.clear()


def _audio_file(
    content: bytes,
    filename: str = "clip.wav",
    content_type: str = "audio/wav",
) -> dict:
    return {
        "audio": (filename, io.BytesIO(content), content_type),
    }


def test_transcribe_authenticated_valid_audio_returns_transcript(transcribe_client) -> None:
    client, provider = transcribe_client
    audio = b"RIFF....wav-content"

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(audio, filename="note.m4a", content_type="audio/mp4"),
    )

    assert response.status_code == 200
    assert response.json() == {"text": "recognized speech"}
    assert len(provider.calls) == 1
    called_bytes, called_filename, called_content_type = provider.calls[0]
    assert called_bytes == audio
    assert called_filename == "note.m4a"
    assert called_content_type == "audio/mp4"


def test_transcribe_unauthenticated_returns_401(db_session, fake_embedding_service) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    with TestClient(app) as test_client:
        response = test_client.post(
            "/assistant/transcribe",
            files=_audio_file(b"audio"),
        )
    app.dependency_overrides.clear()
    assert response.status_code == 401


def test_transcribe_empty_audio_returns_422(transcribe_client) -> None:
    client, provider = transcribe_client

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(b"", filename="clip.wav"),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "audio is empty"
    assert provider.calls == []


def test_transcribe_unsupported_format_returns_422(transcribe_client) -> None:
    client, provider = transcribe_client

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(b"data", filename="clip.txt", content_type="text/plain"),
    )

    assert response.status_code == 422
    assert "unsupported audio format" in response.json()["detail"]
    assert provider.calls == []


def test_transcribe_oversized_audio_returns_413(transcribe_client, monkeypatch) -> None:
    client, provider = transcribe_client
    monkeypatch.setattr(
        "app.assistant.transcription_audio.MAX_TRANSCRIPTION_AUDIO_BYTES",
        64,
    )

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(b"x" * 65, filename="clip.wav"),
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "audio exceeds size limit"
    assert provider.calls == []


def test_transcribe_missing_configuration_returns_502(
    db_session,
    fake_embedding_service,
    auth_headers,
    monkeypatch,
) -> None:
    from tests.conftest import AuthTestClient

    monkeypatch.setattr("app.core.config.settings.openai_api_key", "")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    with TestClient(app) as test_client:
        client = AuthTestClient(test_client, auth_headers)
        response = client.post(
            "/assistant/transcribe",
            files=_audio_file(b"audio-bytes"),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["detail"] == "Transcription provider unavailable"


def test_transcribe_provider_exception_returns_502(transcribe_client) -> None:
    client, provider = transcribe_client

    def failing_transcribe(*_args, **_kwargs):
        raise TranscriptionProviderError("transcription call failed")

    provider.transcribe = failing_transcribe

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(b"audio-bytes"),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Transcription provider unavailable"


def test_openai_transcription_provider_passes_model_and_file_metadata(monkeypatch) -> None:
    captured: dict = {}

    class FakeAudio:
        def __init__(self):
            self.transcriptions = self

        def create(self, **kwargs):
            captured.update(kwargs)
            return MagicMock(text="hello from openai")

    class FakeClient:
        def __init__(self, api_key):
            self.audio = FakeAudio()

    monkeypatch.setattr("openai.OpenAI", lambda api_key: FakeClient(api_key))

    provider = OpenAITranscriptionProvider(
        api_key="sk-test",
        model="gpt-4o-mini-transcribe",
    )
    text = provider.transcribe(
        b"wav-bytes",
        "recording.webm",
        "audio/webm",
    )

    assert text == "hello from openai"
    assert captured["model"] == "gpt-4o-mini-transcribe"
    file_payload = captured["file"]
    assert file_payload[0] == "recording.webm"
    assert file_payload[1] == b"wav-bytes"
    assert file_payload[2] == "audio/webm"


def test_transcribe_does_not_create_db_state(transcribe_client, db_session) -> None:
    client, _ = transcribe_client
    before_objects = db_session.scalar(select(func.count()).select_from(Object))
    before_edges = db_session.scalar(select(func.count()).select_from(Edge))
    before_jobs = db_session.scalar(select(func.count()).select_from(Job))

    response = client.post(
        "/assistant/transcribe",
        files=_audio_file(b"audio-bytes"),
    )

    assert response.status_code == 200
    assert db_session.scalar(select(func.count()).select_from(Object)) == before_objects
    assert db_session.scalar(select(func.count()).select_from(Edge)) == before_edges
    assert db_session.scalar(select(func.count()).select_from(Job)) == before_jobs


def test_read_bounded_transcription_audio_rejects_at_max_plus_one(monkeypatch) -> None:
    from app.assistant.transcription_audio import read_bounded_transcription_audio
    from app.services.errors import ValidationError

    class FakeUpload:
        filename = "clip.wav"
        content_type = "audio/wav"
        _offset = 0
        _data = b"x" * (MAX_TRANSCRIPTION_AUDIO_BYTES + 1)

        async def read(self, size: int) -> bytes:
            chunk = self._data[self._offset : self._offset + size]
            self._offset += len(chunk)
            return chunk

    with pytest.raises(ValidationError, match="audio exceeds size limit"):
        import asyncio

        asyncio.run(read_bounded_transcription_audio(FakeUpload()))


@pytest.mark.live
def test_live_transcription_smoke() -> None:
    import os

    if os.environ.get("RUN_LIVE_OPENAI") != "1":
        pytest.skip("set RUN_LIVE_OPENAI=1 to run live OpenAI smoke")
    from app.core.config import settings
    from app.services.transcription_service import create_transcription_provider

    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured")

    provider = create_transcription_provider()
    # Minimal valid-ish wav header is not required for live test if API accepts bytes
    text = provider.transcribe(b"test", "clip.wav", "audio/wav")
    assert isinstance(text, str)
