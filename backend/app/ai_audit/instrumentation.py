"""Record OpenAI Responses API rounds and tool calls into active AI traces."""

from typing import Any

from app.ai_audit.constants import EVENT_MODEL_ROUND, EVENT_MODEL_ROUND_FAILED, EVENT_TOOL_CALL
from app.ai_audit.context import get_active_trace, maybe_payload_block
from app.ai_audit.payload_accounting import (
    compute_assistant_input_component_sizes,
    extract_responses_usage_fields,
)
from app.llm.openai_usage import response_hit_max_output_tokens


def _response_observable_text(response: object) -> str:
    from app.llm.openai_assistant_provider import _extract_output_text

    text = _extract_output_text(response) or ""
    return text[:32000]


def record_responses_round(
    *,
    response: object | None,
    round_number: int,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    max_output_tokens: int,
    instructions: str,
    input_items: list[dict],
    tool_definitions: list[dict] | None,
    elapsed_ms: int,
    user_message: str | None = None,
    failed: bool = False,
    error_category: str | None = None,
) -> None:
    active = get_active_trace()
    if active is None:
        return

    component_sizes = compute_assistant_input_component_sizes(
        instructions=instructions,
        input_items=input_items,
        tool_definitions=tool_definitions,
        user_message=user_message,
    )
    metadata: dict[str, Any] = {
        "round_number": round_number,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "verbosity": verbosity,
        "max_output_tokens": max_output_tokens,
        "elapsed_ms": elapsed_ms,
        **component_sizes,
    }
    if response is not None:
        usage = extract_responses_usage_fields(response)
        metadata.update(usage)
        metadata["response_chars"] = len(_response_observable_text(response))
        metadata["incomplete_max_output"] = response_hit_max_output_tokens(response)
    if failed:
        metadata["error_category"] = error_category
        payloads = {}
        block = maybe_payload_block("instructions", instructions)
        if block:
            payloads.update(block)
        block = maybe_payload_block("input_items", input_items)
        if block:
            payloads.update(block)
        if tool_definitions is not None:
            block = maybe_payload_block("tool_definitions", tool_definitions)
            if block:
                payloads.update(block)
        if payloads:
            metadata["payloads"] = payloads
        active.record_event(EVENT_MODEL_ROUND_FAILED, metadata)
        return

    payloads = {}
    block = maybe_payload_block("instructions", instructions)
    if block:
        payloads.update(block)
    block = maybe_payload_block("input_items", input_items)
    if block:
        payloads.update(block)
    if tool_definitions is not None:
        block = maybe_payload_block("tool_definitions", tool_definitions)
        if block:
            payloads.update(block)
    block = maybe_payload_block("response_text", _response_observable_text(response))
    if block:
        payloads.update(block)
    if payloads:
        metadata["payloads"] = payloads
    active.record_event(EVENT_MODEL_ROUND, metadata)


def record_tool_execution(
    *,
    tool_name: str,
    validated_arguments: dict,
    success: bool,
    elapsed_ms: int,
    raw_result_chars: int | None,
    model_visible_chars: int | None,
    truncated: bool,
    error_category: str | None = None,
    model_visible_payload: Any = None,
) -> None:
    active = get_active_trace()
    if active is None:
        return
    metadata: dict[str, Any] = {
        "tool_name": tool_name,
        "validated_arguments": validated_arguments,
        "success": success,
        "elapsed_ms": elapsed_ms,
        "raw_result_chars": raw_result_chars,
        "model_visible_chars": model_visible_chars,
        "truncated": truncated,
        "error_category": error_category,
    }
    if model_visible_payload is not None:
        block = maybe_payload_block("model_visible_output", model_visible_payload)
        if block:
            metadata["payloads"] = block
    active.record_event(EVENT_TOOL_CALL, metadata)


def record_simple_model_call(
    *,
    model: str,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    max_output_tokens: int | None = None,
    input_chars: int,
    output_chars: int,
    elapsed_ms: int,
    response: object | None = None,
    failed: bool = False,
    error_category: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    active = get_active_trace()
    if active is None:
        return
    metadata: dict[str, Any] = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "verbosity": verbosity,
        "max_output_tokens": max_output_tokens,
        "request_chars": input_chars,
        "response_chars": output_chars,
        "elapsed_ms": elapsed_ms,
    }
    if response is not None:
        metadata.update(extract_responses_usage_fields(response))
    if extra:
        metadata.update(extra)
    if failed:
        metadata["error_category"] = error_category
        active.record_event(EVENT_MODEL_ROUND_FAILED, metadata)
    else:
        active.record_event(EVENT_MODEL_ROUND, metadata)
