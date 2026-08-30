"""PHASE 23D-A — frozen pending action plans and exact approval execution."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.assistant import get_assistant_provider
from app.api.deps import get_db, get_embedding_service
from app.api.schemas import ObjectCreate
from app.assistant.action_plan_constants import (
    PENDING_ACTION_PLAN_STATUS_EXECUTED,
    PENDING_ACTION_PLAN_STATUS_FAILED,
    PENDING_ACTION_PLAN_STATUS_PENDING,
    PENDING_ACTION_PLAN_STATUS_REJECTED,
)
from app.assistant.session import run_assistant_tool
from app.assistant.tool_runner import BoundAssistantToolRunner, PerTurnToolBudget
from app.db.models import Edge, Object, PendingActionPlan, User
from app.llm.assistant_models import AssistantHistoryMessage, AssistantProviderResult
from app.main import app
from app.services.graph_service import GraphService
from app.tools.execution_context import ExecutionContext
from app.tools.policy import PolicyDecision, ToolPermission, evaluate_policy
from app.tools.results import ToolExecutionStatus
from tests.conftest import AuthTestClient


class _MutationOnlyProvider:
    def __init__(self, tool_name: str, arguments: dict, answer: str = "Proposed action.") -> None:
        self._tool_name = tool_name
        self._arguments = arguments
        self._answer = answer

    def run(
        self,
        message: str,
        history: list[AssistantHistoryMessage],
        ui_context: str,
        reference_datetime: datetime,
        timezone: str,
        tool_runner,
    ) -> AssistantProviderResult:
        tool_runner(self._tool_name, self._arguments)
        return AssistantProviderResult(
            answer=self._answer,
            candidate_object_ids=[],
            affected_object_ids=[],
            store_false_used=True,
        )


class _ReadThenMutateProvider:
    def run(
        self,
        message: str,
        history: list[AssistantHistoryMessage],
        ui_context: str,
        reference_datetime: datetime,
        timezone: str,
        tool_runner,
    ) -> AssistantProviderResult:
        tool_runner("get_today", {})
        tool_runner(
            "create_task",
            {
                "title": "Staged task",
                "confidence": 0.85,
            },
        )
        return AssistantProviderResult(
            answer="I propose creating a task.",
            candidate_object_ids=[],
            affected_object_ids=[],
            store_false_used=True,
        )


class _MultiMutationProvider:
    def __init__(self, calls: list[tuple[str, dict]]) -> None:
        self._calls = calls

    def run(
        self,
        message: str,
        history: list[AssistantHistoryMessage],
        ui_context: str,
        reference_datetime: datetime,
        timezone: str,
        tool_runner,
    ) -> AssistantProviderResult:
        for tool_name, arguments in self._calls:
            tool_runner(tool_name, arguments)
        return AssistantProviderResult(
            answer="Proposed multiple actions.",
            candidate_object_ids=[],
            affected_object_ids=[],
            store_false_used=True,
        )


class _FailingProvider:
    def run(self, *args, **kwargs):
        from app.llm.openai_assistant_provider import AssistantProviderError

        raise AssistantProviderError("provider failed")


@pytest.fixture
def action_plan_user(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, display_name="action plan user"))
    db_session.flush()
    return user_id


@pytest.fixture
def action_plan_client(db_session, fake_embedding_service, action_plan_user, issue_bearer):
    bearer = issue_bearer(action_plan_user)
    headers = {"Authorization": f"Bearer {bearer}"}

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service

    with TestClient(app) as test_client:
        yield AuthTestClient(test_client, headers), action_plan_user
    app.dependency_overrides.clear()


def _task_count(db_session, user_id: uuid.UUID) -> int:
    return db_session.scalar(
        select(func.count()).select_from(Object).where(
            Object.user_id == user_id,
            Object.kind == "task",
        )
    )


def test_interactive_policy_requires_approval_for_internal_write():
    assert (
        evaluate_policy(ToolPermission.INTERNAL_WRITE, ExecutionContext.INTERACTIVE_ASSISTANT)
        == PolicyDecision.REQUIRE_APPROVAL
    )
    assert evaluate_policy(ToolPermission.READ, ExecutionContext.INTERACTIVE_ASSISTANT) == (
        PolicyDecision.ALLOW
    )


def test_interactive_create_task_does_not_mutate(db_session, fake_embedding_service):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, display_name="mutation gate"))
    db_session.flush()
    before = _task_count(db_session, user_id)
    result = run_assistant_tool(
        user_id,
        "create_task",
        {"title": "Blocked task", "confidence": 0.9},
    )
    assert result.success is False
    assert result.status == ToolExecutionStatus.APPROVAL_REQUIRED
    assert result.staged_action is not None
    assert result.staged_action["arguments"]["title"] == "Blocked task"
    after = _task_count(db_session, user_id)
    assert after == before


def test_per_turn_budget_stages_validated_action(db_session, fake_embedding_service, action_plan_user):
    budget = PerTurnToolBudget()
    runner = BoundAssistantToolRunner(budget, action_plan_user)
    result = runner(
        "create_task",
        {"title": "Budget staged", "confidence": 0.8},
    )
    assert result.status == ToolExecutionStatus.APPROVAL_REQUIRED
    assert len(budget.staged_actions) == 1
    assert budget.staged_actions[0]["arguments"]["title"] == "Budget staged"


def test_invalid_evidence_not_staged(db_session, fake_embedding_service, action_plan_user):
    budget = PerTurnToolBudget()
    runner = BoundAssistantToolRunner(budget, action_plan_user)
    unseen = uuid.uuid4()
    result = runner(
        "create_task",
        {
            "title": "Bad evidence",
            "confidence": 0.8,
            "evidence_object_ids": [str(unseen)],
        },
    )
    assert result.success is False
    assert result.status == ToolExecutionStatus.TOOL_ERROR
    assert budget.staged_actions == []


def test_assistant_message_returns_pending_plan(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    provider = _MutationOnlyProvider(
        "create_task",
        {"title": "Exact title", "confidence": 0.91},
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    before = _task_count(db_session, user_id)
    response = client.post(
        "/assistant/message",
        json={"message": "Создай задачу разобраться с этим"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pending_action_plan"] is not None
    plan = body["pending_action_plan"]
    assert plan["status"] == PENDING_ACTION_PLAN_STATUS_PENDING
    assert plan["actions"][0]["tool_name"] == "create_task"
    assert plan["actions"][0]["arguments"]["title"] == "Exact title"
    assert _task_count(db_session, user_id) == before


def test_approve_executes_exact_frozen_arguments(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    provider = _MutationOnlyProvider(
        "create_task",
        {"title": "Frozen exact", "confidence": 0.77, "body": "keep me"},
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    message_response = client.post("/assistant/message", json={"message": "create"})
    plan_id = message_response.json()["pending_action_plan"]["id"]

    approve_response = client.post(f"/assistant/action-plans/{plan_id}/approve")
    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["status"] == PENDING_ACTION_PLAN_STATUS_EXECUTED
    tasks = db_session.scalars(
        select(Object).where(Object.user_id == user_id, Object.kind == "task")
    ).all()
    assert len(tasks) == 1
    assert tasks[0].title == "Frozen exact"
    assert tasks[0].body == "keep me"


def test_repeat_approve_is_idempotent(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    provider = _MutationOnlyProvider(
        "create_task",
        {"title": "Once only", "confidence": 0.7},
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    plan_id = client.post("/assistant/message", json={"message": "create"}).json()[
        "pending_action_plan"
    ]["id"]
    first = client.post(f"/assistant/action-plans/{plan_id}/approve")
    second = client.post(f"/assistant/action-plans/{plan_id}/approve")
    assert first.status_code == 200
    assert second.status_code == 200
    assert _task_count(db_session, user_id) == 1


def test_reject_produces_zero_mutation(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    provider = _MutationOnlyProvider(
        "create_task",
        {"title": "Rejected task", "confidence": 0.7},
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    before = _task_count(db_session, user_id)
    plan_id = client.post("/assistant/message", json={"message": "create"}).json()[
        "pending_action_plan"
    ]["id"]
    response = client.post(f"/assistant/action-plans/{plan_id}/reject")
    assert response.status_code == 200
    assert response.json()["status"] == PENDING_ACTION_PLAN_STATUS_REJECTED
    assert _task_count(db_session, user_id) == before


def test_wrong_user_cannot_approve_plan(
    db_session, fake_embedding_service, action_plan_user, action_plan_client, issue_bearer
):
    client, _ = action_plan_client
    other_user = uuid.uuid4()
    db_session.add(User(id=other_user, display_name="other"))
    db_session.flush()
    other_bearer = issue_bearer(other_user)
    other_headers = {"Authorization": f"Bearer {other_bearer}"}

    provider = _MutationOnlyProvider(
        "create_task",
        {"title": "Private", "confidence": 0.7},
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    plan_id = client.post("/assistant/message", json={"message": "create"}).json()[
        "pending_action_plan"
    ]["id"]

    with TestClient(app) as test_client:
        other_client = AuthTestClient(test_client, other_headers)
        response = other_client.post(f"/assistant/action-plans/{plan_id}/approve")
    assert response.status_code == 404


def test_expired_plan_does_not_execute(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    plan = PendingActionPlan(
        user_id=user_id,
        status=PENDING_ACTION_PLAN_STATUS_PENDING,
        actions=[
            {
                "tool_name": "create_task",
                "permission": "INTERNAL_WRITE",
                "arguments": {"title": "Expired", "confidence": 0.5},
            }
        ],
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(plan)
    db_session.flush()

    before = _task_count(db_session, user_id)
    response = client.post(f"/assistant/action-plans/{plan.id}/approve")
    assert response.status_code == 409
    assert _task_count(db_session, user_id) == before


def test_read_tools_still_execute_during_interactive_turn(action_plan_user):
    budget = PerTurnToolBudget()
    runner = BoundAssistantToolRunner(budget, action_plan_user)
    result = runner("get_today", {})
    assert result.success is True
    assert result.status == ToolExecutionStatus.SUCCESS


def test_provider_failure_does_not_leave_pending_plan(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, _ = action_plan_client
    app.dependency_overrides[get_assistant_provider] = lambda: _FailingProvider()

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    response = client.post("/assistant/message", json={"message": "create"})
    assert response.status_code == 502
    count = db_session.scalar(select(func.count()).select_from(PendingActionPlan))
    assert count == 0


def test_multi_action_plan_commits_atomically(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    client, user_id = action_plan_client
    graph = GraphService(db_session, user_id)
    source = graph.create_object(
        ObjectCreate(kind="note", title="Source", origin="user")
    )
    target = graph.create_object(
        ObjectCreate(kind="note", title="Target", origin="user")
    )
    db_session.flush()

    provider = _MultiMutationProvider(
        [
            (
                "create_task",
                {"title": "Atomic A", "confidence": 0.8},
            ),
            (
                "link_objects",
                {
                    "source_id": str(source.id),
                    "target_id": str(target.id),
                    "relation_type": "references",
                    "confidence": 0.9,
                },
            ),
        ]
    )

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    app.dependency_overrides[get_assistant_provider] = lambda: provider
    import app.services.assistant_service as assistant_service_module

    assistant_service_module.SessionLocal = lambda: _TestSession()

    plan_id = client.post("/assistant/message", json={"message": "do two things"}).json()[
        "pending_action_plan"
    ]["id"]
    approve = client.post(f"/assistant/action-plans/{plan_id}/approve")
    assert approve.status_code == 200
    assert _task_count(db_session, user_id) == 1
    edge_count = db_session.scalar(
        select(func.count()).select_from(Edge).where(Edge.user_id == user_id)
    )
    assert edge_count == 1


def test_failed_action_plan_rolls_back_internal_mutations(
    db_session, fake_embedding_service, action_plan_user, action_plan_client
):
    from app.services.action_plan_service import ActionPlanService

    client, user_id = action_plan_client
    bogus_source = uuid.uuid4()
    bogus_target = uuid.uuid4()
    plan = ActionPlanService(db_session, user_id).create_plan(
        [
            {
                "tool_name": "create_task",
                "permission": "INTERNAL_WRITE",
                "arguments": {"title": "Should rollback", "confidence": 0.8},
            },
            {
                "tool_name": "link_objects",
                "permission": "INTERNAL_WRITE",
                "arguments": {
                    "source_id": str(bogus_source),
                    "target_id": str(bogus_target),
                    "relation_type": "references",
                    "confidence": 0.9,
                },
            },
        ]
    )
    db_session.flush()
    before = _task_count(db_session, user_id)
    failed_view = ActionPlanService(db_session, user_id).approve(plan.id)
    assert failed_view.status == PENDING_ACTION_PLAN_STATUS_FAILED
    assert _task_count(db_session, user_id) == before
    response = client.post(f"/assistant/action-plans/{plan.id}/approve")
    assert response.status_code == 409
