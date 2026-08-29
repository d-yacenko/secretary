from uuid import UUID

import app.assistant.session as assistant_session
from app.assistant.turn_telemetry import AssistantTurnTelemetry
from app.tools.executor import DEFAULT_MAX_TOOL_CALLS, ToolExecutionResult


class PerTurnToolBudget:
    def __init__(
        self,
        max_calls: int = DEFAULT_MAX_TOOL_CALLS,
        telemetry: AssistantTurnTelemetry | None = None,
    ) -> None:
        self._max_calls = max_calls
        self._calls = 0
        self._telemetry = telemetry

    @property
    def calls_made(self) -> int:
        return self._calls

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
        result = assistant_session.run_assistant_tool(user_id, tool_name, arguments)
        if self._telemetry is not None:
            if result.success:
                self._telemetry.record_tool(tool_name, result.output)
            else:
                self._telemetry.tool_calls += 1
        return result
