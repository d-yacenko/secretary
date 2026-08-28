import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.api.schemas import ObjectCreate
from app.db.models import Edge, Object
from app.llm.embedding_service import FakeEmbeddingService
from app.services.domain_tool_service import DomainToolService
from app.services.graph_service import GraphService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE
from app.tools.executor import ToolExecutor
from app.tools.schemas import (
    CreateTaskInput,
    GetContextInput,
    GetObjectInput,
    LinkObjectsInput,
    ListNeighborsInput,
    SearchObjectsInput,
    UpdateTaskInput,
)


@pytest.fixture
def fake_embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def domain_tools(db_session, fake_embedding_service) -> DomainToolService:
    return DomainToolService(db_session, fake_embedding_service)


def _create_task(graph: GraphService, title: str) -> Object:
    return graph.create_object(
        ObjectCreate(kind="task", title=title, origin="user")
    )


def test_search_objects_reads_existing_objects(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    _create_task(graph, "Find me unique alpha marker")

    result = domain_tools.search_objects(
        SearchObjectsInput(query="alpha marker", limit=10)
    )
    assert len(result.objects) >= 1
    assert any(obj["title"] == "Find me unique alpha marker" for obj in result.objects)


def test_get_object_returns_one_object(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    task = _create_task(graph, "Single object lookup")

    result = domain_tools.get_object(GetObjectInput(object_id=task.id))
    assert result.object["id"] == str(task.id)
    assert result.object["title"] == "Single object lookup"


def test_get_context_returns_bounded_context(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    task = _create_task(graph, "Bounded context task")

    result = domain_tools.get_context(
        GetContextInput(object_id=task.id, max_chars=200)
    )
    assert result.total_chars <= 200
    assert len(result.items) >= 1


def test_list_neighbors_returns_graph_neighbors(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    left = _create_task(graph, "Neighbor left")
    right = _create_task(graph, "Neighbor right")
    from app.api.schemas import EdgeCreate

    graph.create_edge(
        EdgeCreate(
            source_id=left.id,
            target_id=right.id,
            type="related_to",
            origin="system",
            state="observed",
        )
    )

    result = domain_tools.list_neighbors(ListNeighborsInput(object_id=left.id))
    assert result.object_id == left.id
    assert len(result.neighbors) == 1
    assert result.neighbors[0].object["id"] == str(right.id)


def test_create_task_creates_agent_proposed_task_with_confidence(
    db_session, domain_tools
) -> None:
    result = domain_tools.create_task(
        CreateTaskInput(title="Agent inferred task", confidence=0.77)
    )
    obj = result.object
    assert obj["kind"] == "task"
    assert obj["origin"] == AGENT_ORIGIN
    assert obj["state"] == PROPOSED_STATE
    assert obj["confidence"] == 0.77


def test_link_objects_creates_agent_proposed_edge_with_confidence(
    db_session, domain_tools
) -> None:
    graph = GraphService(db_session)
    source = _create_task(graph, "Link source")
    target = _create_task(graph, "Link target")

    result = domain_tools.link_objects(
        LinkObjectsInput(
            source_id=source.id,
            target_id=target.id,
            relation_type="related_to",
            confidence=0.66,
        )
    )
    edge = result.edge
    assert edge["origin"] == AGENT_ORIGIN
    assert edge["state"] == PROPOSED_STATE
    assert edge["confidence"] == 0.66


def test_update_task_cannot_rewrite_origin(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    task = _create_task(graph, "Immutable origin task")

    updated = domain_tools.update_task(
        UpdateTaskInput(object_id=task.id, title="Renamed task")
    )
    assert updated.object["title"] == "Renamed task"
    assert updated.object["origin"] == "user"
    assert "origin" not in UpdateTaskInput.model_fields


def test_read_tools_do_not_mutate_db_state(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    task = _create_task(graph, "Read only task")
    before_objects = db_session.scalar(select(func.count()).select_from(Object))
    before_edges = db_session.scalar(select(func.count()).select_from(Edge))

    domain_tools.search_objects(SearchObjectsInput(query="Read only"))
    domain_tools.get_object(GetObjectInput(object_id=task.id))
    domain_tools.get_context(GetContextInput(object_id=task.id, max_chars=500))
    domain_tools.list_neighbors(ListNeighborsInput(object_id=task.id))

    after_objects = db_session.scalar(select(func.count()).select_from(Object))
    after_edges = db_session.scalar(select(func.count()).select_from(Edge))
    assert before_objects == after_objects
    assert before_edges == after_edges


def test_invalid_object_id_returns_controlled_tool_error(db_session, domain_tools) -> None:
    missing_id = uuid.uuid4()
    executor = ToolExecutor(domain_tools, max_calls=5)
    result = executor.execute("get_object", {"object_id": str(missing_id)})
    assert not result.success
    assert result.error


def test_tool_call_limit_prevents_infinite_loop(db_session, domain_tools) -> None:
    graph = GraphService(db_session)
    task = _create_task(graph, "Limit task")
    executor = ToolExecutor(domain_tools, max_calls=5)

    for _ in range(5):
        ok = executor.execute("get_object", {"object_id": str(task.id)})
        assert ok.success

    blocked = executor.execute("get_object", {"object_id": str(task.id)})
    assert not blocked.success
    assert blocked.limit_reached
    assert executor.calls_made == 5
