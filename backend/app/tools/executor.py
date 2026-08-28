from typing import Any

from pydantic import BaseModel

from app.services.domain_tool_service import DomainToolService
from app.tools.schemas import (
    CreateTaskInput,
    GetContextInput,
    GetObjectInput,
    LinkObjectsInput,
    ListNeighborsInput,
    SearchObjectsInput,
    ToolError,
    ToolResult,
    UpdateTaskInput,
)

DEFAULT_MAX_TOOL_CALLS = 5


class ToolExecutionResult(BaseModel):
    success: bool
    tool_name: str
    output: dict[str, Any] | None = None
    error: str | None = None
    limit_reached: bool = False


class ToolExecutor:
    def __init__(
        self,
        tools: DomainToolService,
        max_calls: int = DEFAULT_MAX_TOOL_CALLS,
    ) -> None:
        self._tools = tools
        self._max_calls = max_calls
        self._calls = 0

    @property
    def calls_made(self) -> int:
        return self._calls

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if self._calls >= self._max_calls:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="tool call limit reached",
                limit_reached=True,
            )
        self._calls += 1
        try:
            output = _dispatch(self._tools, tool_name, arguments)
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                output=output.model_dump(mode="json"),
            )
        except ToolError as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=exc.message,
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"tool execution failed: {type(exc).__name__}",
            )


def _dispatch(tools: DomainToolService, tool_name: str, arguments: dict[str, Any]):
    if tool_name == "search_objects":
        return tools.search_objects(SearchObjectsInput.model_validate(arguments))
    if tool_name == "get_object":
        return tools.get_object(GetObjectInput.model_validate(arguments))
    if tool_name == "get_context":
        return tools.get_context(GetContextInput.model_validate(arguments))
    if tool_name == "list_neighbors":
        return tools.list_neighbors(ListNeighborsInput.model_validate(arguments))
    if tool_name == "create_task":
        return tools.create_task(CreateTaskInput.model_validate(arguments))
    if tool_name == "update_task":
        return tools.update_task(UpdateTaskInput.model_validate(arguments))
    if tool_name == "link_objects":
        return tools.link_objects(LinkObjectsInput.model_validate(arguments))
    raise ToolError(f"unknown tool: {tool_name}")
