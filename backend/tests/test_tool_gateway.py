"""Tests for canonical tool registry, policy, and execution gateway."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.assistant.tool_definitions import TOOL_DEFINITIONS
from app.assistant.tool_runner import PerTurnToolBudget
from app.llm.openai_assistant_provider import OpenAIAssistantProvider
from app.tools.gateway import ToolExecutionGateway
from app.tools.policy import PolicyDecision, ToolPermission, evaluate_policy
from app.tools.registry import (
    ASSISTANT_TOOL_DEFINITIONS,
    MCP_TOOL_NAMES,
    TOOL_REGISTRY,
    TOOL_SPECS,
    registered_tool_names,
)
from app.tools.results import ToolExecutionStatus
from app.tools.schemas import ToolError

_EXPECTED_ASSISTANT_TOOL_NAMES = frozenset(
    {
        "retrieve",
        "get_object",
        "get_context",
        "list_neighbors",
        "list_notifications",
        "create_task",
        "update_task",
        "link_objects",
        "get_today",
    }
)


def test_tool_specs_names_are_unique_before_registry_dict():
    names = [spec.name for spec in TOOL_SPECS]
    assert len(names) == len(set(names))


def test_tool_registry_size_matches_tool_specs():
    assert len(TOOL_SPECS) == len(TOOL_REGISTRY)


def test_registry_tool_names_are_unique():
    names = [spec.name for spec in TOOL_REGISTRY.values()]
    assert len(names) == len(set(names))


def test_registry_covers_executor_dispatch_tools():
    expected = {
        "search_objects",
        "retrieve",
        "get_object",
        "get_context",
        "list_neighbors",
        "list_notifications",
        "create_task",
        "update_task",
        "link_objects",
        "get_today",
    }
    assert registered_tool_names() == expected


def test_assistant_tool_definitions_derived_from_registry_exposure():
    registry_assistant = {
        name for name, spec in TOOL_REGISTRY.items() if spec.assistant_exposed
    }
    assert registry_assistant == _EXPECTED_ASSISTANT_TOOL_NAMES
    assert {item["name"] for item in ASSISTANT_TOOL_DEFINITIONS} == _EXPECTED_ASSISTANT_TOOL_NAMES
    assert TOOL_DEFINITIONS is ASSISTANT_TOOL_DEFINITIONS
    assert "search_objects" not in registry_assistant
    assert "retrieve" in registry_assistant


def test_openai_provider_uses_registry_assistant_definitions():
    import inspect

    source = inspect.getsource(OpenAIAssistantProvider.run)
    assert "ASSISTANT_TOOL_DEFINITIONS" in source
    assert "tool_definitions" not in source


def test_mcp_exposed_tools_match_registry():
    assert MCP_TOOL_NAMES == frozenset(
        name for name, spec in TOOL_REGISTRY.items() if spec.mcp_exposed
    )
    assert "search_objects" in MCP_TOOL_NAMES
    assert "retrieve" not in MCP_TOOL_NAMES


def test_permission_classifications():
    read_tools = {
        "retrieve",
        "search_objects",
        "get_object",
        "get_context",
        "list_neighbors",
        "list_notifications",
        "get_today",
    }
    internal_write = {"create_task", "update_task", "link_objects"}
    for name in read_tools:
        assert TOOL_REGISTRY[name].permission == ToolPermission.READ
    for name in internal_write:
        assert TOOL_REGISTRY[name].permission == ToolPermission.INTERNAL_WRITE


def test_baseline_policy_allows_read_and_internal_write():
    assert evaluate_policy(ToolPermission.READ) == PolicyDecision.ALLOW
    assert evaluate_policy(ToolPermission.INTERNAL_WRITE) == PolicyDecision.ALLOW
    assert evaluate_policy(ToolPermission.EXTERNAL_PROPOSE) == PolicyDecision.ALLOW


def test_baseline_policy_requires_approval_for_external_classes():
    assert evaluate_policy(ToolPermission.EXTERNAL_WRITE) == PolicyDecision.REQUIRE_APPROVAL
    assert evaluate_policy(ToolPermission.COMMUNICATE) == PolicyDecision.REQUIRE_APPROVAL


def test_gateway_executes_read_tool():
    tools = MagicMock()
    tools.get_today.return_value = MagicMock(model_dump=lambda mode: {"now": "2026-01-01"})
    gateway = ToolExecutionGateway()
    result = gateway.execute(tools, "get_today", {})
    assert result.success is True
    assert result.status == ToolExecutionStatus.SUCCESS
    tools.get_today.assert_called_once()


def test_gateway_executes_internal_write_tool():
    tools = MagicMock()
    output = MagicMock()
    output.model_dump = lambda mode: {"object": {"id": "task-1", "title": "Task"}}
    tools.create_task.return_value = output
    gateway = ToolExecutionGateway()
    result = gateway.execute(
        tools,
        "create_task",
        {
            "title": "Task",
            "confidence": 0.9,
            "evidence_object_ids": [],
        },
    )
    assert result.success is True
    assert result.status == ToolExecutionStatus.SUCCESS
    tools.create_task.assert_called_once()


def test_gateway_require_approval_does_not_call_handler():
    tools = MagicMock()
    gateway = ToolExecutionGateway()
    original = TOOL_REGISTRY["create_task"]

    class _BlockedSpec:
        name = "blocked_write"
        permission = ToolPermission.EXTERNAL_WRITE
        input_model = original.input_model
        service_method = "create_task"

    TOOL_REGISTRY["blocked_write"] = _BlockedSpec()
    try:
        result = gateway.execute(
            tools,
            "blocked_write",
            {
                "title": "Task",
                "confidence": 0.9,
                "evidence_object_ids": [],
            },
        )
    finally:
        del TOOL_REGISTRY["blocked_write"]

    assert result.success is False
    assert result.approval_required is True
    assert result.status == ToolExecutionStatus.APPROVAL_REQUIRED
    tools.create_task.assert_not_called()


def test_gateway_policy_deny_does_not_call_handler(monkeypatch):
    tools = MagicMock()
    gateway = ToolExecutionGateway()

    monkeypatch.setattr(
        "app.tools.gateway.evaluate_policy",
        lambda permission, context=None: PolicyDecision.DENY,
    )

    result = gateway.execute(
        tools,
        "create_task",
        {
            "title": "Task",
            "confidence": 0.9,
            "evidence_object_ids": [],
        },
    )

    assert result.success is False
    assert result.policy_denied is True
    assert result.status == ToolExecutionStatus.POLICY_DENIED
    tools.create_task.assert_not_called()


def test_gateway_unknown_tool_is_safe():
    tools = MagicMock()
    gateway = ToolExecutionGateway()
    result = gateway.execute(tools, "not_a_real_tool", {})
    assert result.success is False
    assert result.status == ToolExecutionStatus.UNKNOWN_TOOL
    assert "unknown tool" in (result.error or "")


def test_dispatch_raises_tool_error_for_unknown_tool():
    from app.tools.executor import _dispatch

    tools = MagicMock()
    with pytest.raises(ToolError, match="unknown tool"):
        _dispatch(tools, "missing_tool", {})


def test_per_turn_budget_limit_result_status():
    budget = PerTurnToolBudget(max_calls=0)
    result = budget.run(uuid4(), "get_today", {})
    assert result.success is False
    assert result.status == ToolExecutionStatus.LIMIT_REACHED


def test_per_turn_budget_invalid_evidence_result_status():
    budget = PerTurnToolBudget()
    result = budget.run(
        uuid4(),
        "create_task",
        {
            "title": "Task",
            "confidence": 0.9,
            "evidence_object_ids": ["not-a-uuid"],
        },
    )
    assert result.success is False
    assert result.status == ToolExecutionStatus.TOOL_ERROR


def test_per_turn_budget_unseen_evidence_result_status():
    budget = PerTurnToolBudget()
    unseen_id = uuid4()
    result = budget.run(
        uuid4(),
        "create_task",
        {
            "title": "Task",
            "confidence": 0.9,
            "evidence_object_ids": [str(unseen_id)],
        },
    )
    assert result.success is False
    assert result.status == ToolExecutionStatus.TOOL_ERROR


def test_per_turn_budget_success_preserves_gateway_status(monkeypatch):
    from app.tools.results import ToolExecutionResult

    gateway_result = ToolExecutionResult(
        success=True,
        tool_name="get_today",
        output={"now": "2026-01-01"},
        status=ToolExecutionStatus.SUCCESS,
        raw_output=MagicMock(),
    )
    monkeypatch.setattr(
        "app.assistant.session.run_assistant_tool",
        lambda *_: gateway_result,
    )
    budget = PerTurnToolBudget()
    result = budget.run(uuid4(), "get_today", {})
    assert result.success is True
    assert result.status == ToolExecutionStatus.SUCCESS
    assert result.model_output_json is not None
