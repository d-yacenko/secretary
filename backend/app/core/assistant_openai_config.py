from dataclasses import dataclass

from app.core.config import Settings

ALLOWED_ASSISTANT_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high"})
ALLOWED_ASSISTANT_VERBOSITY = frozenset({"low", "medium", "high"})
MIN_ASSISTANT_MAX_OUTPUT_TOKENS = 64
MAX_ASSISTANT_MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class AssistantOpenAISettings:
    model: str
    reasoning_effort: str
    verbosity: str
    max_output_tokens: int


class AssistantOpenAIConfigError(ValueError):
    pass


def validated_assistant_openai_settings(settings: Settings) -> AssistantOpenAISettings:
    model = settings.openai_assistant_model.strip()
    if not model:
        raise AssistantOpenAIConfigError("OPENAI_ASSISTANT_MODEL cannot be blank")

    reasoning_effort = settings.openai_assistant_reasoning_effort.strip().lower()
    if reasoning_effort not in ALLOWED_ASSISTANT_REASONING_EFFORTS:
        allowed = ", ".join(sorted(ALLOWED_ASSISTANT_REASONING_EFFORTS))
        raise AssistantOpenAIConfigError(
            f"OPENAI_ASSISTANT_REASONING_EFFORT must be one of: {allowed}"
        )

    verbosity = settings.openai_assistant_verbosity.strip().lower()
    if verbosity not in ALLOWED_ASSISTANT_VERBOSITY:
        allowed = ", ".join(sorted(ALLOWED_ASSISTANT_VERBOSITY))
        raise AssistantOpenAIConfigError(
            f"OPENAI_ASSISTANT_VERBOSITY must be one of: {allowed}"
        )

    max_output_tokens = settings.openai_assistant_max_output_tokens
    if not MIN_ASSISTANT_MAX_OUTPUT_TOKENS <= max_output_tokens <= MAX_ASSISTANT_MAX_OUTPUT_TOKENS:
        raise AssistantOpenAIConfigError(
            f"OPENAI_ASSISTANT_MAX_OUTPUT_TOKENS must be between "
            f"{MIN_ASSISTANT_MAX_OUTPUT_TOKENS} and {MAX_ASSISTANT_MAX_OUTPUT_TOKENS}"
        )

    return AssistantOpenAISettings(
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        max_output_tokens=max_output_tokens,
    )
