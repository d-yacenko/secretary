"""Structured tool execution outcomes."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    TOOL_ERROR = "tool_error"
    EXECUTION_FAILED = "execution_failed"
    LIMIT_REACHED = "limit_reached"
    APPROVAL_REQUIRED = "approval_required"
    POLICY_DENIED = "policy_denied"
    UNKNOWN_TOOL = "unknown_tool"


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    tool_name: str
    output: dict[str, Any] | None = None
    error: str | None = None
    limit_reached: bool = False
    approval_required: bool = False
    policy_denied: bool = False
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCESS
    model_output_json: str | None = None
    model_visible_payload: dict[str, Any] | None = None
    raw_output: Any = Field(default=None, exclude=True)
