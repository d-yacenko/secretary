import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.assistant import get_assistant_provider
from app.api.deps import get_db, get_embedding_service
from app.api.schemas import ObjectCreate
from app.assistant.session import assistant_tool_session
from app.db.models import Object, User
from app.llm.assistant_models import AssistantProviderResult
from app.llm.embedding_service import FakeEmbeddingService
from app.llm.fake_assistant_provider import FakeAssistantProvider
from app.main import app
from app.services.assistant_service import AssistantService, create_fake_assistant_provider
from app.services.domain_tool_service import DomainToolService
from app.services.errors import NotFoundError
from app.services.graph_service import GraphService
from app.services.notification_service import NotificationService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE
from app.tools.executor import DEFAULT_MAX_TOOL_CALLS, ToolExecutionResult, ToolExecutor
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture(autouse=True)
def patch_assistant_tool_session(db_session, fake_embedding_service, monkeypatch):
    @contextmanager
    def test_tool_session(user_id):
        yield DomainToolService(db_session, user_id, fake_embedding_service)

    monkeypatch.setattr("app.assistant.session.assistant_tool_session", test_tool_session)
    monkeypatch.setattr("app.services.assistant_service.assistant_tool_session", test_tool_session)

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    monkeypatch.setattr(
        "app.services.assistant_service.SessionLocal",
        lambda: _TestSession(),
    )


@pytest.fixture
def fake_assistant_provider() -> FakeAssistantProvider:
    return create_fake_assistant_provider()


@pytest.fixture
def assistant_client(db_session, fake_embedding_service, auth_headers, fake_assistant_provider):
    from tests.conftest import AuthTestClient

    def override_get_db():
        yield db_session

    def override_provider():
        return fake_assistant_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    app.dependency_overrides[get_assistant_provider] = override_provider
    with TestClient(app) as test_client:
        yield AuthTestClient(test_client, auth_headers), fake_assistant_provider
    app.dependency_overrides.clear()


def _create_task(graph: GraphService, title: str, status: str | None = None) -> object:
    return graph.create_object(
        ObjectCreate(
            kind="task",
            title=title,
            origin="user",
            status=status,
        )
    )


def test_assistant_requires_auth(db_session, fake_embedding_service) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    app.dependency_overrides[get_assistant_provider] = create_fake_assistant_provider
    with TestClient(app) as client:
        response = client.post(
            "/assistant/message",
            json={"message": "hello"},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 401


def test_assistant_rejects_user_id(assistant_client) -> None:
    client, _ = assistant_client
    response = client.post(
        "/assistant/message",
        json={"message": "hello", "user_id": "evil"},
    )
    assert response.status_code == 422


def test_assistant_rejects_blank_message(assistant_client) -> None:
    client, _ = assistant_client
    response = client.post("/assistant/message", json={"message": "   "})
    assert response.status_code == 422


def test_assistant_rejects_oversized_message(assistant_client) -> None:
    client, _ = assistant_client
    response = client.post("/assistant/message", json={"message": "x" * 8001})
    assert response.status_code == 422


def test_assistant_rejects_oversized_history(assistant_client) -> None:
    client, _ = assistant_client
    history = [
        {"role": "user", "content": "a" * 3000},
        {"role": "assistant", "content": "b" * 3000},
        {"role": "user", "content": "c" * 3000},
        {"role": "assistant", "content": "d" * 3000},
        {"role": "user", "content": "e" * 3000},
        {"role": "assistant", "content": "f" * 3000},
        {"role": "user", "content": "g" * 3000},
        {"role": "assistant", "content": "h" * 3000},
        {"role": "user", "content": "i" * 3000},
    ]
    response = client.post(
        "/assistant/message",
        json={"message": "hello", "history": history},
    )
    assert response.status_code == 422


def test_assistant_project_alpha_read_scenario(
    db_session, assistant_client, fake_embedding_service
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    project = graph.create_object(
        ObjectCreate(kind="project", title="Project Alpha", origin="user")
    )
    pending = _create_task(graph, "Pending outline for Project Alpha", status="pending")

    client, provider = assistant_client
    response = client.post(
        "/assistant/message",
        json={"message": "What is pending for Project Alpha?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "Project Alpha" in payload["answer"]
    reference_ids = {item["object_id"] for item in payload["references"]}
    assert str(pending.id) in reference_ids or str(project.id) in reference_ids
    assert any(call[0] == "search_objects" for call in provider.calls)


def test_assistant_context_object_scenario(
    db_session, assistant_client, fake_embedding_service
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    course = graph.create_object(
        ObjectCreate(kind="course", title="Intro Course", origin="user", body="Syllabus draft")
    )

    client, provider = assistant_client
    response = client.post(
        "/assistant/message",
        json={
            "message": "What is this related to?",
            "context_object_id": str(course.id),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert str(course.id) in {item["object_id"] for item in payload["references"]}
    assert any(call[0] == "get_context" for call in provider.calls)


def test_assistant_create_task_write_regression(
    db_session, assistant_client, fake_embedding_service, user_b_id
) -> None:
    client, _ = assistant_client
    response = client.post(
        "/assistant/message",
        json={"message": "Create a task to prepare the course outline."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["affected_objects"]
    affected = payload["affected_objects"][0]
    assert affected["kind"] == "task"
    assert affected["state"] == PROPOSED_STATE

    obj = db_session.get(Object, uuid.UUID(affected["object_id"]))
    assert obj is not None
    assert obj.user_id == BOOTSTRAP_USER_ID
    assert obj.origin == AGENT_ORIGIN

    graph_b = GraphService(db_session, user_b_id, fake_embedding_service)

    with pytest.raises(NotFoundError):
        graph_b.get_object(uuid.UUID(affected["object_id"]))


def test_assistant_cross_user_context_object_returns_404(
    db_session, assistant_client, fake_embedding_service, user_b_id
) -> None:
    graph_b = GraphService(db_session, user_b_id, fake_embedding_service)
    other_task = _create_task(graph_b, "User B private task")

    client, _ = assistant_client
    response = client.post(
        "/assistant/message",
        json={
            "message": "What is this?",
            "context_object_id": str(other_task.id),
        },
    )
    assert response.status_code == 404


def test_assistant_cross_user_notification_returns_404(
    db_session, assistant_client, user_b_id
) -> None:
    service_b = NotificationService(db_session, user_b_id)
    notification = service_b.create(
        title="User B alert",
        body="secret",
        priority="normal",
        proposal={"type": "task", "description": "hidden"},
    )

    client, _ = assistant_client
    response = client.post(
        "/assistant/message",
        json={
            "message": "Why is this important?",
            "context_notification_id": str(notification.id),
        },
    )
    assert response.status_code == 404


def test_assistant_foreign_object_id_not_returned(
    db_session, assistant_client, fake_embedding_service, user_b_id
) -> None:
    graph_b = GraphService(db_session, user_b_id, fake_embedding_service)
    other_task = _create_task(graph_b, "Foreign task marker")

    class ForeignIdProvider(FakeAssistantProvider):
        def run(self, message, history, ui_context, reference_datetime, timezone, tool_runner):
            result = super().run(
                message, history, ui_context, reference_datetime, timezone, tool_runner
            )
            return AssistantProviderResult(
                answer=result.answer,
                candidate_object_ids=[other_task.id],
                affected_object_ids=[],
                store_false_used=True,
            )

    def override_provider():
        return ForeignIdProvider()

    app.dependency_overrides[get_assistant_provider] = override_provider
    client, _ = assistant_client
    response = client.post("/assistant/message", json={"message": "hello"})
    assert response.status_code == 200
    reference_ids = {item["object_id"] for item in response.json()["references"]}
    assert str(other_task.id) not in reference_ids


def test_assistant_tool_call_limit_bounded(db_session, fake_embedding_service) -> None:
    tools = DomainToolService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    executor = ToolExecutor(tools, max_calls=DEFAULT_MAX_TOOL_CALLS)
    for _ in range(DEFAULT_MAX_TOOL_CALLS):
        result = executor.execute("get_today", {})
        assert result.success
    blocked = executor.execute("get_today", {})
    assert not blocked.success
    assert blocked.limit_reached


def test_assistant_fake_provider_store_false(fake_assistant_provider) -> None:
    result = fake_assistant_provider.run(
        message="hello",
        history=[],
        ui_context="",
        reference_datetime=datetime.now(timezone.utc),
        timezone="Europe/Amsterdam",
        tool_runner=lambda *_: ToolExecutionResult(success=True, tool_name="get_today", output={}),
    )
    assert result.store_false_used


def test_assistant_db_session_not_open_during_provider_gap(
    db_session, fake_embedding_service, monkeypatch
) -> None:
    open_sessions: list[object] = []

    @contextmanager
    def tracking_tool_session(user_id):
        with assistant_tool_session(user_id) as tools:
            open_sessions.append(tools)
            yield tools
            open_sessions.clear()

    monkeypatch.setattr("app.services.assistant_service.assistant_tool_session", tracking_tool_session)

    class SlowGapProvider(FakeAssistantProvider):
        def run(self, message, history, ui_context, reference_datetime, timezone, tool_runner):
            assert not open_sessions
            tool_runner("get_today", {})
            assert not open_sessions
            time.sleep(0.02)
            assert not open_sessions
            return AssistantProviderResult(
                answer="gap ok",
                candidate_object_ids=[],
                affected_object_ids=[],
                store_false_used=True,
            )

    service = AssistantService(BOOTSTRAP_USER_ID, SlowGapProvider())
    result = service.send_message(message="test gap", history=[])
    assert result.answer == "gap ok"


def test_openai_assistant_provider_uses_store_false(monkeypatch) -> None:
    from app.llm.openai_assistant_provider import OpenAIAssistantProvider

    captured: dict = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            response = MagicMock()
            response.output = []
            response.output_text = "ok"
            return response

    class FakeClient:
        def __init__(self, api_key):
            self.responses = FakeResponses()

    monkeypatch.setattr(
        "openai.OpenAI",
        lambda api_key: FakeClient(api_key),
    )
    provider = OpenAIAssistantProvider(api_key="test-key", model="gpt-test")
    provider.run(
        message="hello",
        history=[],
        ui_context="",
        reference_datetime=datetime.now(timezone.utc),
        timezone="Europe/Amsterdam",
        tool_runner=lambda *_: ToolExecutionResult(success=True, tool_name="get_today", output={}),
    )
    assert captured.get("store") is False


@pytest.fixture
def user_b_id(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, display_name="User B"))
    db_session.flush()
    return user_id
