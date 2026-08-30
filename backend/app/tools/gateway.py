"""Policy-aware gateway between agent tool selection and DomainToolService."""

from typing import Any

from app.services.domain_tool_service import DomainToolService
from app.tools.policy import (
    PolicyDecision,
    evaluate_policy,
    policy_block_message,
)
from app.tools.registry import execute_registered_tool, get_tool_spec
from app.tools.results import ToolExecutionResult, ToolExecutionStatus
from app.tools.schemas import ToolError


class ToolExecutionGateway:
    def execute(
        self,
        tools: DomainToolService,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        spec = get_tool_spec(tool_name)
        if spec is None:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"unknown tool: {tool_name}",
                status=ToolExecutionStatus.UNKNOWN_TOOL,
            )

        decision = evaluate_policy(spec.permission)
        if decision == PolicyDecision.REQUIRE_APPROVAL:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=policy_block_message(decision),
                approval_required=True,
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
            )
        if decision == PolicyDecision.DENY:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=policy_block_message(decision),
                policy_denied=True,
                status=ToolExecutionStatus.POLICY_DENIED,
            )

        try:
            output_model = execute_registered_tool(tools, spec, arguments)
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                output=output_model.model_dump(mode="json"),
                status=ToolExecutionStatus.SUCCESS,
                raw_output=output_model,
            )
        except ToolError as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=exc.message,
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"tool execution failed: {type(exc).__name__}",
                status=ToolExecutionStatus.EXECUTION_FAILED,
            )
