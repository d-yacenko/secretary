class TranscriptionProviderError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class OpenAITranscriptionProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None,
    ) -> str:
        file_payload = (
            filename,
            audio_bytes,
            content_type or "application/octet-stream",
        )
        try:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=file_payload,
            )
        except Exception as exc:
            raise TranscriptionProviderError("transcription call failed") from exc

        text = getattr(response, "text", None)
        if not text:
            raise TranscriptionProviderError("transcription returned empty text")
        return str(text)
