import logging
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from pydantic import ValidationError as PydanticValidationError

from app.mcp.gateway_runner import execute_mcp_tool
from app.tools.registry import MCP_TOOL_NAMES  # noqa: F401 — re-exported for tests
from app.tools.schemas import (
    CreateTaskOutput,
    DeleteTaskOutput,
    GetContextOutput,
    GetObjectOutput,
    GetTodayOutput,
    LinkObjectsOutput,
    ListNeighborsOutput,
    ListNotificationsOutput,
    QueryObjectsOutput,
    RemoveRelationOutput,
    SearchObjectsOutput,
    SetTaskStatusOutput,
    ToolError,
    UpdateTaskOutput,
)

logger = logging.getLogger(__name__)


def _run_tool(operation: str, tool_name: str, arguments: dict) -> object:
    try:
        return execute_mcp_tool(tool_name, arguments)
    except ToolError as exc:
        logger.warning("mcp tool %s failed: %s", operation, exc.message)
        raise McpToolError(exc.message) from exc
    except PydanticValidationError:
        logger.warning("mcp tool %s rejected invalid input", operation)
        raise McpToolError("invalid tool input") from None
    except ValueError:
        logger.warning("mcp tool %s rejected invalid value", operation)
        raise McpToolError("invalid tool input") from None
    except Exception:
        logger.exception("mcp tool %s unexpected failure", operation)
        raise McpToolError(f"{operation} failed") from None


def create_mcp_server() -> MCPServer:
    mcp = MCPServer(
        "personal-secretary",
        instructions="Personal Secretary domain tools over the internal object graph.",
    )

    @mcp.tool()
    def query_objects(
        kinds: list[str] | None = None,
        providers: list[str] | None = None,
        statuses: list[str] | None = None,
        states: list[str] | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
    ) -> QueryObjectsOutput:
        """Structured object query with filters and deterministic ordering."""
        arguments: dict = {
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": limit,
        }
        if kinds is not None:
            arguments["kinds"] = kinds
        if providers is not None:
            arguments["providers"] = providers
        if statuses is not None:
            arguments["statuses"] = statuses
        if states is not None:
            arguments["states"] = states
        if due_from is not None:
            arguments["due_from"] = due_from
        if due_to is not None:
            arguments["due_to"] = due_to
        if start_from is not None:
            arguments["start_from"] = start_from
        if start_to is not None:
            arguments["start_to"] = start_to
        if occurred_from is not None:
            arguments["occurred_from"] = occurred_from
        if occurred_to is not None:
            arguments["occurred_to"] = occurred_to
        return _run_tool("query_objects", "query_objects", arguments)

    @mcp.tool()
    def search_objects(
        query: str,
        kind: str | None = None,
        limit: int = 20,
    ) -> SearchObjectsOutput:
        """Search objects by semantic and lexical match."""
        return _run_tool(
            "search_objects",
            "search_objects",
            {"query": query, "kind": kind, "limit": limit},
        )

    @mcp.tool()
    def get_object(object_id: str) -> GetObjectOutput:
        """Fetch one object by id."""
        return _run_tool(
            "get_object",
            "get_object",
            {"object_id": object_id},
        )

    @mcp.tool()
    def get_context(
        object_id: str | None = None,
        query: str | None = None,
        max_chars: int = 8000,
    ) -> GetContextOutput:
        """Build bounded context using the Context Resolver."""
        return _run_tool(
            "get_context",
            "get_context",
            {
                "object_id": object_id,
                "query": query,
                "max_chars": max_chars,
            },
        )

    @mcp.tool()
    def list_neighbors(object_id: str) -> ListNeighborsOutput:
        """List direct graph neighbors for an object."""
        return _run_tool(
            "list_neighbors",
            "list_neighbors",
            {"object_id": object_id},
        )

    @mcp.tool()
    def create_task(
        title: str,
        confidence: float,
        body: str | None = None,
        due_at: datetime | None = None,
        evidence_object_ids: list[str] | None = None,
    ) -> CreateTaskOutput:
        """Create an agent-proposed task with required confidence."""
        return _run_tool(
            "create_task",
            "create_task",
            {
                "title": title,
                "confidence": confidence,
                "body": body,
                "due_at": due_at,
                "evidence_object_ids": evidence_object_ids or [],
            },
        )

    @mcp.tool()
    def update_task(
        object_id: str,
        title: str | None = None,
        body: str | None = None,
        due_at: datetime | None = None,
        evidence_object_ids: list[str] | None = None,
    ) -> UpdateTaskOutput:
        """Update task fields or attach evidence without changing lifecycle status."""
        arguments: dict = {"object_id": object_id}
        if title is not None:
            arguments["title"] = title
        if body is not None:
            arguments["body"] = body
        if due_at is not None:
            arguments["due_at"] = due_at
        if evidence_object_ids is not None:
            arguments["evidence_object_ids"] = evidence_object_ids
        return _run_tool("update_task", "update_task", arguments)

    @mcp.tool()
    def set_task_status(object_id: str, status: str) -> SetTaskStatusOutput:
        """Set canonical task lifecycle status."""
        return _run_tool(
            "set_task_status",
            "set_task_status",
            {"object_id": object_id, "status": status},
        )

    @mcp.tool()
    def delete_task(object_id: str) -> DeleteTaskOutput:
        """Soft-delete a task (status=deleted)."""
        return _run_tool(
            "delete_task",
            "delete_task",
            {"object_id": object_id},
        )

    @mcp.tool()
    def link_objects(
        source_id: str,
        target_id: str,
        relation_type: str,
        confidence: float,
    ) -> LinkObjectsOutput:
        """Create an agent-proposed relation between two objects."""
        return _run_tool(
            "link_objects",
            "link_objects",
            {
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "confidence": confidence,
            },
        )

    @mcp.tool()
    def remove_relation(edge_id: str) -> RemoveRelationOutput:
        """Deactivate a semantic graph relation by exact edge_id (requires approval)."""
        return _run_tool(
            "remove_relation",
            "remove_relation",
            {"edge_id": edge_id},
        )

    @mcp.tool()
    def list_notifications(
        status: str | None = None,
        limit: int = 50,
    ) -> ListNotificationsOutput:
        """List inbox notifications with optional status filter."""
        return _run_tool(
            "list_notifications",
            "list_notifications",
            {"status": status, "limit": limit},
        )

    @mcp.tool()
    def get_today() -> GetTodayOutput:
        """Return the current datetime in SECRETARY_TIMEZONE."""
        return _run_tool("get_today", "get_today", {})

    return mcp
