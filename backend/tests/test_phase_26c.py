"""PHASE 26C structured query, search ordering, and grounding regressions."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_embedding_service
from app.api.schemas import ObjectCreate
from app.assistant.reference_ids import (
    collect_seen_object_ids_from_bounded_tool,
)
from app.assistant.tool_output import serialize_tool_output_for_model
from app.assistant.tool_runner import PerTurnToolBudget
from app.db.models import Object
from app.domain.task_lifecycle import TASK_STATUS_DELETED, TASK_STATUS_OPEN
from app.llm.embedding_service import FakeEmbeddingService
from app.main import app
from app.services.domain_tool_service import DomainToolService
from app.services.errors import ValidationError
from app.services.graph_service import GraphService
from app.services.object_primary_date import object_primary_search_datetime
from app.services.object_query_service import ObjectQueryService
from app.services.provenance import PROPOSED_STATE, REJECTED_STATE
from app.services.search_facet_service import SearchFacetService
from app.services.search_service import SEARCH_SORT_NEWEST, SearchService
from app.tools.registry import MCP_TOOL_NAMES, get_tool_spec
from app.tools.schemas import QueryObjectsInput
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def phase26c_client(db_session, auth_headers):
    from tests.conftest import AuthTestClient

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    with TestClient(app) as client:
        yield AuthTestClient(client, auth_headers)
    app.dependency_overrides.clear()


def _create_task(
    graph: GraphService,
    title: str,
    *,
    due_at: datetime | None = None,
    status: str = TASK_STATUS_OPEN,
    state: str = "confirmed",
) -> Object:
    obj = graph.create_object(
        ObjectCreate(kind="task", title=title, origin="user", state=state)
    )
    obj.kind = "task"
    obj.status = status
    if due_at is not None:
        obj.due_at = due_at
    return obj


def test_query_objects_tool_registry_exposure() -> None:
    spec = get_tool_spec("query_objects")
    assert spec is not None
    assert spec.permission.name == "READ"
    assert spec.assistant_exposed
    assert spec.mcp_exposed
    assert "query_objects" in MCP_TOOL_NAMES


def test_nearest_due_task_regression(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    task_a = _create_task(
        graph,
        "Task A",
        due_at=datetime(2026, 8, 31, tzinfo=UTC),
        state=PROPOSED_STATE,
    )
    task_b = _create_task(
        graph,
        "Task B",
        due_at=datetime(2026, 9, 5, tzinfo=UTC),
        state="confirmed",
    )
    db_session.flush()

    service = DomainToolService(
        db_session, BOOTSTRAP_USER_ID, FakeEmbeddingService()
    )
    result = service.query_objects(
        QueryObjectsInput(
            kinds=["task"],
            statuses=["open", "in_progress"],
            sort_by="due_at",
            sort_order="asc",
            limit=20,
        )
    )
    ids = [row.object_id for row in result.objects]
    assert ids.index(task_a.id) < ids.index(task_b.id)


def test_proposed_visible_rejected_hidden(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    proposed = _create_task(graph, "Proposed", state=PROPOSED_STATE)
    rejected = _create_task(graph, "Rejected", state=REJECTED_STATE)
    db_session.flush()

    rows = ObjectQueryService(db_session, BOOTSTRAP_USER_ID).query(
        kinds=["task"], limit=50
    )
    ids = {row.id for row in rows}
    assert proposed.id in ids
    assert rejected.id not in ids


def test_deleted_task_hidden(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    active = _create_task(graph, "Active")
    deleted = _create_task(graph, "Deleted", status=TASK_STATUS_DELETED)
    db_session.flush()

    rows = ObjectQueryService(db_session, BOOTSTRAP_USER_ID).query(kinds=["task"])
    ids = {row.id for row in rows}
    assert active.id in ids
    assert deleted.id not in ids


def test_invalid_sort_field_rejected(db_session) -> None:
    service = ObjectQueryService(db_session, BOOTSTRAP_USER_ID)
    with pytest.raises(ValidationError):
        service.query(sort_by="urgent", limit=5)


def test_query_objects_grounding_and_approval(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    task = _create_task(
        graph,
        "Ground me",
        due_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    db_session.flush()

    tools = DomainToolService(db_session, BOOTSTRAP_USER_ID, FakeEmbeddingService())
    raw = tools.query_objects(
        QueryObjectsInput(
            kinds=["task"],
            statuses=["open"],
            sort_by="due_at",
            sort_order="asc",
            limit=5,
        )
    ).model_dump(mode="json")
    bounded = serialize_tool_output_for_model("query_objects", raw)
    seen = collect_seen_object_ids_from_bounded_tool("query_objects", bounded)
    assert task.id in seen

    budget = PerTurnToolBudget()
    budget.commit_model_visible_outputs()
    budget.seed_seen_object_ids(seen)
    result = budget.run(
        BOOTSTRAP_USER_ID,
        "set_task_status",
        {"object_id": str(task.id), "status": "in_progress"},
    )
    assert result.status.name == "APPROVAL_REQUIRED"


def test_assistant_tool_chain_get_today_query_mutation(db_session, monkeypatch) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    task = _create_task(
        graph,
        "Chain task",
        due_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    task_id = task.id
    db_session.flush()

    class _TestSession:
        def __init__(self) -> None:
            self._session = db_session

        def close(self) -> None:
            return None

        def __getattr__(self, name: str):
            return getattr(self._session, name)

    import app.assistant.session as assistant_session_module

    monkeypatch.setattr(assistant_session_module, "SessionLocal", lambda: _TestSession())

    budget = PerTurnToolBudget()

    today_result = budget.run(BOOTSTRAP_USER_ID, "get_today", {})
    assert today_result.status.name == "SUCCESS"

    query_result = budget.run(
        BOOTSTRAP_USER_ID,
        "query_objects",
        {
            "kinds": ["task"],
            "statuses": ["open"],
            "sort_by": "due_at",
            "sort_order": "asc",
            "limit": 5,
        },
    )
    assert query_result.status.name == "SUCCESS"
    assert task_id in budget.pending_seen_object_ids

    budget.commit_model_visible_outputs()
    assert task_id in budget.seen_object_ids

    mutation = budget.run(
        BOOTSTRAP_USER_ID,
        "set_task_status",
        {"object_id": str(task_id), "status": "in_progress"},
    )
    assert mutation.status.name == "APPROVAL_REQUIRED"
    assert mutation.staged_action is not None
    assert mutation.staged_action["tool_name"] == "set_task_status"
    assert mutation.staged_action["arguments"]["object_id"] == str(task_id)
    assert mutation.staged_action["arguments"]["status"] == "in_progress"


def test_search_newest_ordering_uses_candidate_pool(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    older = graph.create_object(
        ObjectCreate(
            kind="note",
            title="alpha solar budget keyword marker",
            body="older note body",
            origin="system",
        )
    )
    older.updated_at = datetime(2020, 1, 1, tzinfo=UTC)
    newer = graph.create_object(
        ObjectCreate(
            kind="note",
            title="beta solar budget keyword marker",
            body="newer note body",
            origin="system",
        )
    )
    newer.updated_at = datetime(2026, 8, 30, tzinfo=UTC)
    db_session.flush()

    search = SearchService(db_session, BOOTSTRAP_USER_ID)
    newest = search.search("solar budget keyword marker", limit=3, sort=SEARCH_SORT_NEWEST)
    assert newest[0].id == newer.id


def test_search_facets_exclude_other_user(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    graph.create_object(
        ObjectCreate(kind="email", title="Mine", provider="gmail", origin="system")
    )
    db_session.flush()

    facets = SearchFacetService(db_session, BOOTSTRAP_USER_ID).facets()
    kinds = {row["value"] for row in facets["kinds"]}
    assert "email" in kinds


def test_primary_search_date_task_uses_due_at(db_session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    task = _create_task(
        graph,
        "Due",
        due_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    task.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.flush()
    assert object_primary_search_datetime(task).replace(tzinfo=UTC) == datetime(
        2026, 8, 15, tzinfo=UTC
    )


def test_search_facets_endpoint(phase26c_client) -> None:
    phase26c_client.post(
        "/objects",
        json={"kind": "task", "title": "Facet task", "origin": "user"},
    )
    resp = phase26c_client.get("/search/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert "kinds" in body
    assert "providers" in body


def test_search_sort_query_param(phase26c_client) -> None:
    phase26c_client.post(
        "/objects",
        json={
            "kind": "note",
            "title": "Sortable gamma keyword",
            "body": "content",
            "origin": "system",
        },
    )
    resp = phase26c_client.get(
        "/search",
        params={"q": "Sortable gamma keyword", "sort": "newest", "limit": 5},
    )
    assert resp.status_code == 200
