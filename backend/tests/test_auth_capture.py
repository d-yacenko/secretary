import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.api.deps import get_db
from app.api.schemas import EdgeCreate, ObjectCreate
from app.auth.token_service import AuthTokenService
from app.db.models import Edge, Object, User
from app.llm.embedding_service import FakeEmbeddingService
from app.main import app
from app.services.capture_service import PINNED_CONTEXT_ROLE
from app.services.context_service import ContextService, DEFAULT_MAX_CHARS
from app.services.graph_service import GraphService
from app.users.bootstrap import BOOTSTRAP_USER_ID


def _create_user(db_session, name: str = "Alt user") -> uuid.UUID:
    user = User(id=uuid.uuid4(), display_name=name)
    db_session.add(user)
    db_session.flush()
    return user.id


def test_unauthenticated_api_returns_401() -> None:
    client = TestClient(app)
    response = client.get("/me")
    assert response.status_code == 401


def test_invalid_token_returns_401(db_session) -> None:
    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_revoked_token_returns_401(db_session, issue_bearer) -> None:
    token = issue_bearer(BOOTSTRAP_USER_ID, label="revoke-me")
    AuthTokenService(db_session).revoke_by_prefix(BOOTSTRAP_USER_ID, "revoke-me")
    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_get_me_returns_safe_fields(auth_client) -> None:
    response = auth_client.get("/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(BOOTSTRAP_USER_ID)
    assert body["display_name"] == "Owner"
    assert "created_at" in body
    assert "token" not in body


def test_two_tokens_resolve_to_isolated_users(db_session, issue_bearer) -> None:
    user_b = _create_user(db_session, "User B")
    token_a = issue_bearer(BOOTSTRAP_USER_ID, label="user-a")
    token_b = issue_bearer(user_b, label="user-b")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        me_a = client.get("/me", headers={"Authorization": f"Bearer {token_a}"})
        me_b = client.get("/me", headers={"Authorization": f"Bearer {token_b}"})
        assert me_a.json()["id"] == str(BOOTSTRAP_USER_ID)
        assert me_b.json()["id"] == str(user_b)
    finally:
        app.dependency_overrides.clear()


def test_get_connections_returns_status_without_secrets(auth_client) -> None:
    response = auth_client.get("/connections")
    assert response.status_code == 200
    body = response.json()
    assert "google" in body
    assert "yandex_mail" in body
    assert "yandex_calendar" in body
    dumped = str(body)
    assert "access_token" not in dumped
    assert "refresh_token" not in dumped
    assert "app_password" not in dumped


def test_manual_capture_creates_task_with_pinned_context_and_dependency(
    db_session, auth_client
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    course_plan = graph.create_object(
        ObjectCreate(
            kind="document",
            title="Course plan",
            origin="user",
            state="confirmed",
            canonical_uri="personal://resource/course-plan",
        )
    )
    cloud_folder = graph.create_object(
        ObjectCreate(
            kind="folder",
            title="Training center materials",
            origin="user",
            state="confirmed",
            provider="google_drive",
            canonical_uri="https://drive.google.com/folder/training",
        )
    )
    gmail_source = graph.create_object(
        ObjectCreate(
            kind="email",
            title="Gmail thread",
            origin="source",
            state="confirmed",
            provider="gmail",
            external_id="msg-capture-regression",
            canonical_uri="gmail://msg-capture-regression",
        )
    )
    dependency = graph.create_object(
        ObjectCreate(
            kind="task",
            title="Prerequisite task",
            origin="user",
            state="confirmed",
        )
    )
    db_session.flush()

    manual_text = (
        "Prepare the first three topics of the course.\n"
        "From our training center only I can teach these topics."
    )
    response = auth_client.post(
        "/capture/task",
        json={
            "text": manual_text,
            "context_object_ids": [
                str(course_plan.id),
                str(cloud_folder.id),
                str(gmail_source.id),
            ],
            "depends_on_ids": [str(dependency.id)],
        },
    )
    assert response.status_code == 201
    body = response.json()
    task_id = uuid.UUID(body["task_id"])
    assert len(body["context_edge_ids"]) == 3
    assert len(body["dependency_edge_ids"]) == 1

    task = db_session.get(Object, task_id)
    assert task is not None
    assert task.user_id == BOOTSTRAP_USER_ID
    assert task.kind == "task"
    assert task.origin == "user"
    assert task.state == "confirmed"
    assert task.body == manual_text

    ref_edges = db_session.scalars(
        select(Edge).where(
            Edge.source_id == task_id,
            Edge.type == "references",
            Edge.state == "confirmed",
        )
    ).all()
    assert len(ref_edges) == 3
    for edge in ref_edges:
        assert edge.metadata_["context_role"] == PINNED_CONTEXT_ROLE
        assert edge.metadata_["added_by"] == "user"

    dep_edges = db_session.scalars(
        select(Edge).where(
            Edge.source_id == task_id,
            Edge.type == "depends_on",
            Edge.state == "confirmed",
        )
    ).all()
    assert len(dep_edges) == 1
    assert dep_edges[0].target_id == dependency.id


def test_manual_capture_context_prioritizes_pinned_over_semantic(
    db_session, fake_embedding_service
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    pinned_doc = graph.create_object(
        ObjectCreate(
            kind="document",
            title="Pinned course syllabus",
            origin="user",
            state="confirmed",
            body="unique pinned syllabus marker alpha",
        )
    )
    semantic_doc = graph.create_object(
        ObjectCreate(
            kind="document",
            title="Semantic competitor document",
            origin="system",
            state="confirmed",
            body="unique semantic competitor marker beta query terms",
        )
    )
    task = graph.create_object(
        ObjectCreate(
            kind="task",
            title="Teach topics",
            origin="user",
            state="confirmed",
            body="Prepare course topics from training center",
        )
    )
    graph.create_edge(
        EdgeCreate(
            source_id=task.id,
            target_id=pinned_doc.id,
            type="references",
            origin="user",
            state="confirmed",
            metadata={"context_role": PINNED_CONTEXT_ROLE, "added_by": "user"},
        )
    )
    db_session.flush()

    context = ContextService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    result = context.build_context(
        object_id=task.id,
        query="unique semantic competitor marker beta query terms",
        max_chars=DEFAULT_MAX_CHARS,
    )
    why_included = [item.why_included for item in result.items]
    assert any("user-pinned" in reason for reason in why_included)
    pinned_index = next(
        i for i, item in enumerate(result.items) if item.object_id == pinned_doc.id
    )
    semantic_index = next(
        (
            i
            for i, item in enumerate(result.items)
            if item.object_id == semantic_doc.id
        ),
        len(result.items),
    )
    if semantic_index < len(result.items):
        assert pinned_index < semantic_index


def test_manual_capture_rejects_cross_user_context(
    db_session, auth_client, issue_bearer
) -> None:
    user_b = _create_user(db_session, "User B")
    graph_b = GraphService(db_session, user_b)
    foreign = graph_b.create_object(
        ObjectCreate(kind="document", title="Foreign doc", origin="user", state="confirmed")
    )
    db_session.flush()

    response = auth_client.post(
        "/capture/task",
        json={
            "text": "Try cross-user capture",
            "context_object_ids": [str(foreign.id)],
        },
    )
    assert response.status_code == 404
    tasks = db_session.scalars(
        select(Object).where(Object.kind == "task", Object.body == "Try cross-user capture")
    ).all()
    assert tasks == []


def test_manual_capture_does_not_require_openai(db_session, auth_client) -> None:
    with patch("app.llm.embedding_service.create_embedding_service") as factory:
        factory.side_effect = RuntimeError("OpenAI unavailable")
        response = auth_client.post(
            "/capture/task",
            json={"text": "Standalone capture without OpenAI"},
        )
    assert response.status_code == 201
    task_id = uuid.UUID(response.json()["task_id"])
    task = db_session.get(Object, task_id)
    assert task is not None
    assert task.body == "Standalone capture without OpenAI"


def test_google_oauth_start_requires_authentication(db_session) -> None:
    client = TestClient(app)
    response = client.get("/auth/google/start", follow_redirects=False)
    assert response.status_code == 401


def test_google_oauth_start_binds_state_to_authenticated_user(
    db_session, issue_bearer
) -> None:
    from sqlalchemy import select

    from app.db.models import OAuthState

    token = issue_bearer(BOOTSTRAP_USER_ID, label="google-oauth")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        with patch("app.api.google._google_oauth_service") as mock_oauth:
            mock_oauth.return_value.build_authorization_url.return_value = "http://redirect"
            response = client.get(
                "/auth/google/start",
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=False,
            )
        assert response.status_code in {302, 307}
        states = db_session.scalars(
            select(OAuthState).where(OAuthState.user_id == BOOTSTRAP_USER_ID)
        ).all()
        assert states
    finally:
        app.dependency_overrides.clear()
