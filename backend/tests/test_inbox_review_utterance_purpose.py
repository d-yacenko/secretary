from app.assistant.inbox_review_intent import (
    COMPLETE_INBOX_REVIEW_UTTERANCES,
    inbox_review_purpose_for_utterance,
)
from app.llm.openai_assistant_provider import SYSTEM_INSTRUCTIONS
from app.tools.assistant_contracts import ASSISTANT_FUNCTION_SCHEMAS


def test_enumerate_all_new_messages_is_purpose_review() -> None:
    assert (
        inbox_review_purpose_for_utterance("перечисли все новые сообщения") == "review"
    )
    assert (
        inbox_review_purpose_for_utterance("Перечисли все новые сообщения.") == "review"
    )


def test_complete_enumeration_utterances_are_purpose_review() -> None:
    for phrase in COMPLETE_INBOX_REVIEW_UTTERANCES:
        assert inbox_review_purpose_for_utterance(phrase) == "review", phrase


def test_count_and_peek_utterances_are_purpose_inspect() -> None:
    assert inbox_review_purpose_for_utterance("сколько новых?") == "inspect"
    assert inbox_review_purpose_for_utterance("сколько новых сообщений?") == "inspect"
    assert inbox_review_purpose_for_utterance("покажи последние два") == "inspect"
    assert inbox_review_purpose_for_utterance("есть что-нибудь новое?") == "inspect"


def test_prompt_and_tool_schema_bind_exact_review_phrase() -> None:
    phrase = "перечисли все новые сообщения"
    assert phrase in SYSTEM_INSTRUCTIONS
    description = ASSISTANT_FUNCTION_SCHEMAS["list_inbox_since_review_marker"]["description"]
    assert phrase in description
    purpose_desc = ASSISTANT_FUNCTION_SCHEMAS["list_inbox_since_review_marker"]["parameters"][
        "properties"
    ]["purpose"]["description"]
    assert phrase in purpose_desc
