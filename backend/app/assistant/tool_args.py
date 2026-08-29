from typing import Any

from app.assistant.constants import (
    MAX_ASSISTANT_CONTEXT_CHARS,
    MAX_ASSISTANT_LIST_RESULTS,
    MAX_ASSISTANT_NEIGHBOR_RESULTS,
    MAX_ASSISTANT_SEARCH_RESULTS,
)
from app.tools.schemas import ToolError


def normalize_assistant_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Clamp Assistant tool arguments before domain execution."""
    if tool_name == "search_objects":
        limit = arguments.get("limit", MAX_ASSISTANT_SEARCH_RESULTS)
        if not isinstance(limit, int):
            raise ToolError("search_objects limit must be an integer")
        if limit < 1:
            raise ToolError("search_objects limit must be at least 1")
        return {
            **arguments,
            "limit": min(limit, MAX_ASSISTANT_SEARCH_RESULTS),
        }

    if tool_name == "list_notifications":
        limit = arguments.get("limit", MAX_ASSISTANT_LIST_RESULTS)
        if not isinstance(limit, int):
            raise ToolError("list_notifications limit must be an integer")
        if limit < 1:
            raise ToolError("list_notifications limit must be at least 1")
        return {
            **arguments,
            "limit": min(limit, MAX_ASSISTANT_LIST_RESULTS),
        }

    if tool_name == "list_neighbors":
        return {
            **arguments,
            "limit": MAX_ASSISTANT_NEIGHBOR_RESULTS,
        }

    if tool_name == "get_context":
        if "query" in arguments:
            raise ToolError("get_context does not accept query; use search_objects first")
        object_id = arguments.get("object_id")
        if not object_id:
            raise ToolError("get_context requires object_id")
        max_chars = arguments.get("max_chars", MAX_ASSISTANT_CONTEXT_CHARS)
        if not isinstance(max_chars, int):
            raise ToolError("get_context max_chars must be an integer")
        if max_chars < 1:
            raise ToolError("get_context max_chars must be at least 1")
        return {
            "object_id": object_id,
            "max_chars": min(max_chars, MAX_ASSISTANT_CONTEXT_CHARS),
        }

    return arguments
