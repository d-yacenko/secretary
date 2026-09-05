from collections.abc import Sequence
from uuid import UUID

import app.assistant.session as assistant_session
from app.assistant.action_plan_constants import MAX_ACTIONS_PER_PLAN
from app.assistant.constants import MAX_ASSISTANT_TOOL_CALLS_PER_TURN
from app.assistant.reference_ids import (
    collect_seen_edge_ids_from_bounded_tool,
    collect_seen_object_ids_from_bounded_tool,
)
from app.assistant.tool_output import serialize_tool_output_for_assistant
from app.assistant.turn_telemetry import AssistantTurnTelemetry
from app.tools.results import ToolExecutionResult, ToolExecutionStatus

_READ_TOOLS = frozenset(
    {
        "retrieve",
        "query_objects",
        "search_objects",
        "get_object",
        "get_context",
        "list_neighbors",
        "list_notifications",
    }
)
_EVIDENCE_WRITE_TOOLS = frozenset(
    {"create_task", "update_task", "set_task_status", "delete_task"}
)
_OBJECT_TARGET_TOOLS = frozenset({"update_task", "set_task_status", "delete_task"})
_MUTATION_TOOLS = frozenset(
    {
        "create_task",
        "update_task",
        "set_task_status",
        "delete_task",
        "link_objects",
        "remove_relation",
        "create_calendar_event",
    }
)


class PerTurnToolBudget:
    def __init__(
        self,
        max_calls: int = MAX_ASSISTANT_TOOL_CALLS_PER_TURN,
        telemetry: AssistantTurnTelemetry | None = None,
        initial_seen_object_ids: Sequence[UUID] | None = None,
    ) -> None:
        self._max_calls = max_calls
        self._calls = 0
        self._telemetry = telemetry
        self._seen_object_ids: set[UUID] = set(initial_seen_object_ids or [])
        self._pending_seen_object_ids: set[UUID] = set()
        self._seen_edge_ids: set[UUID] = set()
        self._pending_seen_edge_ids: set[UUID] = set()
        self._staged_actions: list[dict] = []
        self._plan_sealed = False

    @property
    def calls_made(self) -> int:
        return self._calls

    @property
    def seen_object_ids(self) -> set[UUID]:
        return set(self._seen_object_ids)

    @property
    def pending_seen_object_ids(self) -> set[UUID]:
        return set(self._pending_seen_object_ids)

    @property
    def staged_actions(self) -> list[dict]:
        return list(self._staged_actions)

    def seed_seen_object_ids(self, object_ids: Sequence[UUID]) -> None:
        self._seen_object_ids.update(object_ids)

    def commit_model_visible_outputs(self) -> None:
        """Promote IDs from the last model response after outputs were delivered to input."""
        self._seen_object_ids.update(self._pending_seen_object_ids)
        self._pending_seen_object_ids.clear()
        self._seen_edge_ids.update(self._pending_seen_edge_ids)
        self._pending_seen_edge_ids.clear()
        if self._staged_actions:
            self._plan_sealed = True

    def run(self, user_id: UUID, tool_name: str, arguments: dict) -> ToolExecutionResult:
        if self._calls >= self._max_calls:
            if self._telemetry is not None:
                self._telemetry.tool_calls += 1
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="tool call limit reached",
                limit_reached=True,
                status=ToolExecutionStatus.LIMIT_REACHED,
            )
        self._calls += 1

        if tool_name in _MUTATION_TOOLS:
            if self._plan_sealed:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="action plan already staged for approval",
                    status=ToolExecutionStatus.TOOL_ERROR,
                )
            if len(self._staged_actions) >= MAX_ACTIONS_PER_PLAN:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="action plan exceeds maximum actions",
                    status=ToolExecutionStatus.TOOL_ERROR,
                )

        if tool_name in _EVIDENCE_WRITE_TOOLS:
            evidence_error = self._validate_evidence_allowlist(tool_name, arguments)
            if evidence_error is not None:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return evidence_error

        if tool_name in _OBJECT_TARGET_TOOLS:
            target_error = self._validate_object_target_allowlist(tool_name, arguments)
            if target_error is not None:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return target_error

        if tool_name == "remove_relation":
            edge_error = self._validate_edge_id_allowlist(tool_name, arguments)
            if edge_error is not None:
                if self._telemetry is not None:
                    self._telemetry.tool_calls += 1
                return edge_error

        result = assistant_session.run_assistant_tool(user_id, tool_name, arguments)
        if result.status == ToolExecutionStatus.APPROVAL_REQUIRED and result.staged_action:
            self._stage_action(result.staged_action)
            if self._telemetry is not None:
                self._telemetry.tool_calls += 1
            return result

        if result.success and result.output:
            model_output = serialize_tool_output_for_assistant(tool_name, result.output)
            if tool_name in _READ_TOOLS or tool_name in _EVIDENCE_WRITE_TOOLS:
                for object_id in collect_seen_object_ids_from_bounded_tool(
                    tool_name, model_output.model_visible_payload
                ):
                    self._pending_seen_object_ids.add(object_id)
            for edge_id in collect_seen_edge_ids_from_bounded_tool(
                tool_name, model_output.model_visible_payload
            ):
                self._pending_seen_edge_ids.add(edge_id)
            result = result.model_copy(
                update={
                    "model_output_json": model_output.model_output_json,
                    "model_visible_payload": model_output.model_visible_payload,
                }
            )
            if self._telemetry is not None:
                self._telemetry.record_tool(tool_name, result.output)
        elif self._telemetry is not None:
            self._telemetry.tool_calls += 1
        return result

    def _stage_action(self, staged_action: dict) -> None:
        if self._is_duplicate_action(staged_action):
            return
        self._staged_actions.append(staged_action)

    def _is_duplicate_action(self, staged_action: dict) -> bool:
        for existing in self._staged_actions:
            if (
                existing.get("tool_name") == staged_action.get("tool_name")
                and existing.get("arguments") == staged_action.get("arguments")
            ):
                return True
        return False

    def _validate_evidence_allowlist(
        self, tool_name: str, arguments: dict
    ) -> ToolExecutionResult | None:
        evidence_raw = arguments.get("evidence_object_ids")
        if not evidence_raw:
            return None
        for raw_id in evidence_raw:
            try:
                parsed = UUID(str(raw_id))
            except (ValueError, TypeError):
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="invalid evidence object id",
                    status=ToolExecutionStatus.TOOL_ERROR,
                )
            if parsed not in self._seen_object_ids:
                return ToolExecutionResult(
                    success=False,
                    tool_name=tool_name,
                    error="evidence object was not exposed in this Assistant turn",
                    status=ToolExecutionStatus.TOOL_ERROR,
                )
        return None

    def _validate_object_target_allowlist(
        self, tool_name: str, arguments: dict
    ) -> ToolExecutionResult | None:
        raw_id = arguments.get("object_id")
        if raw_id is None:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="object_id is required",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        try:
            parsed = UUID(str(raw_id))
        except (ValueError, TypeError):
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="invalid object id",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        if parsed not in self._seen_object_ids:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="target object was not exposed in this Assistant turn",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        return None

    def _validate_edge_id_allowlist(
        self, tool_name: str, arguments: dict
    ) -> ToolExecutionResult | None:
        raw_id = arguments.get("edge_id")
        if raw_id is None:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="edge_id is required",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        try:
            parsed = UUID(str(raw_id))
        except (ValueError, TypeError):
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="invalid edge id",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        if parsed not in self._seen_edge_ids:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                error="edge was not exposed in this Assistant turn (use list_neighbors first)",
                status=ToolExecutionStatus.TOOL_ERROR,
            )
        return None


class BoundAssistantToolRunner:
    """Adapter exposing PerTurnToolBudget to the Assistant provider loop."""

    def __init__(self, budget: PerTurnToolBudget, user_id: UUID) -> None:
        self._budget = budget
        self._user_id = user_id

    def __call__(self, tool_name: str, arguments: dict) -> ToolExecutionResult:
        return self._budget.run(self._user_id, tool_name, arguments)

    def commit_model_visible_outputs(self) -> None:
        self._budget.commit_model_visible_outputs()
