"""Structured Assistant API error responses."""

from app.core.assistant_openai_config import AssistantOpenAIConfigError
from app.llm.assistant_provider_errors import (
    ASSISTANT_CONFIGURATION,
    ASSISTANT_INTERNAL,
    USER_MESSAGES,
    AssistantProviderError,
)
from app.services.assistant_service import AssistantConfigurationError
from app.services.user_openai_credential_errors import UserOpenAICredentialConfigurationError


def build_assistant_error_detail(exc: Exception) -> dict[str, str]:
    if isinstance(exc, AssistantProviderError):
        return {"code": exc.code, "message": exc.message}
    if isinstance(
        exc,
        (
            AssistantConfigurationError,
            AssistantOpenAIConfigError,
            UserOpenAICredentialConfigurationError,
        ),
    ):
        return {
            "code": ASSISTANT_CONFIGURATION,
            "message": USER_MESSAGES[ASSISTANT_CONFIGURATION],
        }
    return {
        "code": ASSISTANT_INTERNAL,
        "message": USER_MESSAGES[ASSISTANT_INTERNAL],
    }
