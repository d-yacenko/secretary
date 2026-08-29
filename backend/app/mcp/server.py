import logging
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as McpToolError
from pydantic import ValidationError as PydanticValidationError

from app.mcp.session import tool_session
from app.tools.schemas import (
    CreateTaskInput,
    CreateTaskOutput,
    GetContextInput,
    GetContextOutput,
    GetObjectInput,
    GetObjectOutput,
    GetTodayOutput,
    LinkObjectsInput,
    LinkObjectsOutput,
    ListNeighborsInput,
    ListNeighborsOutput,
    ListNotificationsInput,
    ListNotificationsOutput,
    SearchObjectsInput,
    SearchObjectsOutput,
    ToolError,
    UpdateTaskInput,
    UpdateTaskOutput,
)

logger = logging.getLogger(__name__)

MCP_TOOL_NAMES = frozenset(
    {
        "search_objects",
        "get_object",
        "get_context",
        "list_neighbors",
        "create_task",
        "update_task",
        "link_objects",
        "get_today",
        "list_notifications",
    }
)


def _run_tool(operation: str, fn) -> object:
    try:
        with tool_session() as tools:
            return fn(tools)
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
    def search_objects(
        query: str,
        kind: str | None = None,
        limit: int = 20,
    ) -> SearchObjectsOutput:
        """Search objects by semantic and lexical match."""
        return _run_tool(
            "search_objects",
            lambda tools: tools.search_objects(
                SearchObjectsInput(query=query, kind=kind, limit=limit)
            ),
        )

    @mcp.tool()
    def get_object(object_id: str) -> GetObjectOutput:
        """Fetch one object by id."""
        return _run_tool(
            "get_object",
            lambda tools: tools.get_object(GetObjectInput(object_id=object_id)),
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
            lambda tools: tools.get_context(
                GetContextInput(
                    object_id=object_id,
                    query=query,
                    max_chars=max_chars,
                )
            ),
        )

    @mcp.tool()
    def list_neighbors(object_id: str) -> ListNeighborsOutput:
        """List direct graph neighbors for an object."""
        return _run_tool(
            "list_neighbors",
            lambda tools: tools.list_neighbors(ListNeighborsInput(object_id=object_id)),
        )

    @mcp.tool()
    def create_task(
        title: str,
        confidence: float,
        body: str | None = None,
        due_at: datetime | None = None,
        status: str | None = None,
    ) -> CreateTaskOutput:
        """Create an agent-proposed task with required confidence."""
        return _run_tool(
            "create_task",
            lambda tools: tools.create_task(
                CreateTaskInput(
                    title=title,
                    confidence=confidence,
                    body=body,
                    due_at=due_at,
                    status=status,
                )
            ),
        )

    @mcp.tool()
    def update_task(
        object_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        due_at: datetime | None = None,
    ) -> UpdateTaskOutput:
        """Update a task without changing provenance origin."""
        return _run_tool(
            "update_task",
            lambda tools: tools.update_task(
                UpdateTaskInput(
                    object_id=object_id,
                    title=title,
                    body=body,
                    status=status,
                    due_at=due_at,
                )
            ),
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
            lambda tools: tools.link_objects(
                LinkObjectsInput(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=relation_type,
                    confidence=confidence,
                )
            ),
        )

    @mcp.tool()
    def list_notifications(
        status: str | None = None,
        limit: int = 50,
    ) -> ListNotificationsOutput:
        """List inbox notifications with optional status filter."""
        return _run_tool(
            "list_notifications",
            lambda tools: tools.list_notifications(
                ListNotificationsInput(status=status, limit=limit)
            ),
        )

    @mcp.tool()
    def get_today() -> GetTodayOutput:
        """Return the current datetime in SECRETARY_TIMEZONE."""
        return _run_tool("get_today", lambda tools: tools.get_today())

    return mcp

