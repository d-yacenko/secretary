"""Policy-aware gateway between agent tool selection and DomainToolService."""

from typing import Any

from pydantic import ValidationError

from app.services.domain_tool_service import DomainToolService
from app.tools.execution_context import ExecutionContext
from app.tools.policy import (
    PolicyDecision,
    evaluate_policy,
    policy_block_message,
)
from app.tools.registry import execute_registered_tool, get_tool_spec, validate_tool_arguments
from app.tools.results import ToolExecutionResult, ToolExecutionStatus
from app.tools.schemas import ToolError


class ToolExecutionGateway:
    def execute(
        self,
        tools: DomainToolService,
        tool_name: str,
        arguments: dict[str, Any],
        context: ExecutionContext = ExecutionContext.BASELINE,
    ) -> ToolExecutionResult:
        spec = get_tool_spec(tool_name)
        if spec is None:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=f"unknown tool: {tool_name}",
                status=ToolExecutionStatus.UNKNOWN_TOOL,
            )

        try:
            validated_arguments = validate_tool_arguments(spec, arguments)
        except ValidationError:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="invalid tool input",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        except ToolError as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=exc.message,
                status=ToolExecutionStatus.TOOL_ERROR,
            )

        decision = evaluate_policy(spec.permission, context)
        if decision == PolicyDecision.REQUIRE_APPROVAL:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error=policy_block_message(decision),
                approval_required=True,
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
                staged_action={
                    "tool_name": tool_name,
                    "permission": spec.permission.value,
                    "arguments": validated_arguments,
                },
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
            output_model = execute_registered_tool(tools, spec, validated_arguments)
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
