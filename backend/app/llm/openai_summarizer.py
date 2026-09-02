"""OpenAI semantic summarizer for resource representations."""

import logging

from app.llm.summarizer import Summarizer
from app.services.background_ai_errors import BackgroundAIConfigurationError
from app.services.effective_user_settings_service import EffectiveUserSettings

logger = logging.getLogger(__name__)

_SUMMARY_INSTRUCTIONS = (
    "Summarize the resource in Russian in <=500 characters. "
    "Answer: what is it, what is it about, what role does it appear to have. "
    "No speculation beyond the provided text. No secrets not already in the text."
)


class OpenAISummarizer:
    def __init__(
        self,
        api_key: str,
        model: str,
        reasoning_effort: str = "low",
        verbosity: str = "low",
        max_output_tokens: int = 400,
        max_chars: int = 500,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._verbosity = verbosity
        self._max_output_tokens = max_output_tokens
        self._max_chars = max_chars

    def summarize(self, text: str) -> str:
        bounded = text[:4000]
        response = self._client.responses.create(
            model=self._model,
            instructions=_SUMMARY_INSTRUCTIONS,
            input=bounded,
            reasoning={"effort": self._reasoning_effort},
            text={"verbosity": self._verbosity},
            max_output_tokens=self._max_output_tokens,
        )
        output = _extract_response_text(response).strip()
        if len(output) > self._max_chars:
            return output[: self._max_chars].rstrip() + "…"
        return output


def _extract_response_text(response) -> str:
    for item in response.output or []:
        if item.type == "message":
            for content in item.content or []:
                if content.type == "output_text":
                    return content.text
    return ""


def create_openai_summarizer() -> Summarizer:
    from app.core.config import settings

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI summarizer")
    return OpenAISummarizer(
        api_key=settings.openai_api_key,
        model=settings.openai_assistant_model,
        reasoning_effort=settings.openai_assistant_reasoning_effort,
        verbosity=settings.openai_assistant_verbosity,
    )


def create_openai_summarizer_from_effective(
    effective: EffectiveUserSettings,
) -> Summarizer:
    if not effective.openai_api_key:
        raise BackgroundAIConfigurationError("OpenAI API key is not configured")
    return OpenAISummarizer(
        api_key=effective.openai_api_key,
        model=effective.assistant_model,
        reasoning_effort=effective.assistant_reasoning_effort,
        verbosity=effective.assistant_verbosity,
    )
