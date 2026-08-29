from uuid import UUID

from app.assistant.session import run_assistant_tool
from app.tools.executor import DEFAULT_MAX_TOOL_CALLS, ToolExecutionResult


class PerTurnToolBudget:
    def __init__(self, max_calls: int = DEFAULT_MAX_TOOL_CALLS) -> None:
        self._max_calls = max_calls
        self._calls = 0

    @property
    def calls_made(self) -> int:
        return self._calls

    def run(self, user_id: UUID, tool_name: str, arguments: dict) -> ToolExecutionResult:
        if self._calls >= self._max_calls:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="tool call limit reached",
                limit_reached=True,
            )
        self._calls += 1
        return run_assistant_tool(user_id, tool_name, arguments)
