from collections.abc import Sequence
from uuid import UUID

import app.assistant.session as assistant_session
from app.assistant.reference_ids import collect_seen_object_ids_from_bounded_tool
from app.assistant.tool_output import serialize_tool_output_for_assistant
from app.assistant.turn_telemetry import AssistantTurnTelemetry
from app.tools.executor import DEFAULT_MAX_TOOL_CALLS, ToolExecutionResult

_READ_TOOLS = frozenset(
    {
        "retrieve",
        "search_objects",
        "get_object",
        "get_context",
        "list_neighbors",
        "list_notifications",
    }
)
_EVIDENCE_WRITE_TOOLS = frozenset({"create_task", "update_task"})


class PerTurnToolBudget:
    def __init__(
        self,
        max_calls: int = DEFAULT_MAX_TOOL_CALLS,
        telemetry: AssistantTurnTelemetry | None = None,
        initial_seen_object_ids: Sequence[UUID] | None = None,
    ) -> None:
        self._max_calls = max_calls
        self._calls = 0
        self._telemetry = telemetry
        self._seen_object_ids: set[UUID] = set(initial_seen_object_ids or [])

    @property
    def calls_made(self) -> int:
        return self._calls

    @property
    def seen_object_ids(self) -> set[UUID]:
        return set(self._seen_object_ids)

    def seed_seen_object_ids(self, object_ids: Sequence[UUID]) -> None:
        self._seen_object_ids.update(object_ids)

    def run(self, user_id: UUID, tool_name: str, arguments: dict) -> ToolExecutionResult:
        if self._calls >= self._max_calls:
            if self._telemetry is not None:
                self._telemetry.tool_calls += 1
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="tool call limit reached",
                limit_reached=True,
            )
        self._calls += 1

        if tool_name in _EVIDENCE_WRITE_TOOLS:
            evidence_error = self._validate_evidence_allowlist(tool_name, arguments)
            if evidence_error is not None:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return evidence_error

        result = assistant_session.run_assistant_tool(user_id, tool_name, arguments)
        if result.success and result.output:
            model_output = serialize_tool_output_for_assistant(tool_name, result.output)
            if tool_name in _READ_TOOLS or tool_name in _EVIDENCE_WRITE_TOOLS:
                for object_id in collect_seen_object_ids_from_bounded_tool(
                    tool_name, model_output.model_visible_payload
                ):
                    self._seen_object_ids.add(object_id)
            result = ToolExecutionResult(
                success=result.success,
                tool_name=result.tool_name,
                output=result.output,
                error=result.error,
                limit_reached=result.limit_reached,
                model_output_json=model_output.model_output_json,
                model_visible_payload=model_output.model_visible_payload,
            )
            if self._telemetry is not None:
                self._telemetry.record_tool(tool_name, result.output)
        elif self._telemetry is not None:
            self._telemetry.tool_calls += 1
        return result

    def _validate_evidence_allowlist(
        self, tool_name: str, arguments: dict
    ) -> ToolExecutionResult | None:
        evidence_raw = arguments.get("evidence_object_ids")
        if not evidence_raw:
            return None
        for raw_id in evidence_raw:
            try:
                parsed = UUID(str(raw_id))
            except (ValueError, TypeError):
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="invalid evidence object id",
                )
            if parsed not in self._seen_object_ids:
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="evidence object was not exposed in this Assistant turn",
                )
        return None
