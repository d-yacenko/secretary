from uuid import UUID

from app.assistant.tool_args import normalize_assistant_tool_arguments
from app.db.session import SessionLocal
from app.llm.embedding_service import create_embedding_service
from app.services.domain_tool_service import DomainToolService
from app.tools.executor import ToolExecutionResult, _dispatch
from app.tools.schemas import ToolError


def run_assistant_tool(user_id: UUID, tool_name: str, arguments: dict) -> ToolExecutionResult:
    """One Assistant tool call: short session, commit on success, rollback on failure."""
    session = SessionLocal()
    tools = DomainToolService(
        session,
        user_id,
        create_embedding_service(),
        defer_write_embeddings=True,
    )
    try:
        normalized_arguments = normalize_assistant_tool_arguments(tool_name, arguments)
        output = _dispatch(tools, tool_name, normalized_arguments)
        session.commit()
        return ToolExecutionResult(
            success=True,
            tool_name=tool_name,
            output=output.model_dump(mode="json"),
        )
    except ToolError as exc:
        session.rollback()
        return ToolExecutionResult(
            success=False,
            tool_name=tool_name,
            error=exc.message,
        )
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return ToolExecutionResult(
            success=False,
            tool_name=tool_name,
            error=f"tool execution failed: {type(exc).__name__}",
        )
    finally:
        session.close()
