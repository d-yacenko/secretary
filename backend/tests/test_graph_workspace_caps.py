"""PHASE 24 closure — graph workspace cap and batch neighbor tests."""

from datetime import UTC, datetime

from app.api.schemas import EdgeCreate, ObjectCreate
from app.services.graph_service import GraphService
from app.services.graph_workspace_service import GraphWorkspaceService
from app.services.provenance import CONFIRMED_STATE
from tests.conftest import BOOTSTRAP_USER_ID


def _task(graph: GraphService, title: str, status: str | None = "open") -> object:
    return graph.create_object(
        ObjectCreate(
            kind="task",
            title=title,
            origin="user",
            state=CONFIRMED_STATE,
            status=status,
            due_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        )
    )


def test_overview_node_limit_wins_over_seed_limit(db_session, fake_embedding_service):
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    for index in range(12):
        _task(graph, f"ACTIVE-{index}")
    db_session.flush()

    service = GraphWorkspaceService(db_session, BOOTSTRAP_USER_ID)
    result = service.get_workspace(seed_limit=12, node_limit=5)
    assert len(result.nodes) <= 5
    assert result.truncated is True


def test_twelve_active_tasks_with_node_limit_five(db_session, fake_embedding_service):
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    for index in range(12):
        _task(graph, f"CAP-{index}")
    db_session.flush()

    service = GraphWorkspaceService(db_session, BOOTSTRAP_USER_ID)
    result = service.get_workspace(seed_limit=12, neighbor_limit=12, node_limit=5)
    assert len(result.nodes) == 5
    assert result.truncated is True
    node_ids = {node.id for node in result.nodes}
    for edge in result.edges:
        assert edge.source_id in node_ids
        assert edge.target_id in node_ids


def test_neighbor_limit_enforced(db_session, fake_embedding_service):
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    root = _task(graph, "ROOT")
    for index in range(8):
        neighbor = graph.create_object(
            ObjectCreate(kind="note", title=f"N-{index}", origin="user", state=CONFIRMED_STATE)
        )
        graph.create_edge(
            EdgeCreate(
                source_id=root.id,
                target_id=neighbor.id,
                type="references",
                origin="user",
                state=CONFIRMED_STATE,
            )
        )
    db_session.flush()

    service = GraphWorkspaceService(db_session, BOOTSTRAP_USER_ID)
    result = service.get_workspace(
        root_id=root.id,
        neighbor_limit=3,
        node_limit=80,
    )
    assert len(result.nodes) <= 4
    assert result.truncated is True


def test_cycle_bounded_unique_ids(db_session, fake_embedding_service):
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    a = _task(graph, "A")
    b = _task(graph, "B")
    c = _task(graph, "C")
    graph.create_edge(
        EdgeCreate(
            source_id=a.id,
            target_id=b.id,
            type="related_to",
            origin="user",
            state=CONFIRMED_STATE,
        )
    )
    graph.create_edge(
        EdgeCreate(
            source_id=b.id,
            target_id=c.id,
            type="depends_on",
            origin="user",
            state=CONFIRMED_STATE,
        )
    )
    graph.create_edge(
        EdgeCreate(
            source_id=c.id,
            target_id=a.id,
            type="references",
            origin="user",
            state=CONFIRMED_STATE,
        )
    )
    db_session.flush()

    service = GraphWorkspaceService(db_session, BOOTSTRAP_USER_ID)
    result = service.get_workspace(root_id=a.id, neighbor_limit=12, node_limit=80)
    node_ids = [node.id for node in result.nodes]
    edge_ids = [edge.id for edge in result.edges]
    assert len(node_ids) == len(set(node_ids))
    assert len(edge_ids) == len(set(edge_ids))


def test_duplicate_neighbor_edges_do_not_exceed_node_cap(db_session, fake_embedding_service):
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    seeds = [_task(graph, f"SEED-{index}") for index in range(6)]
    shared = graph.create_object(
        ObjectCreate(kind="note", title="SHARED", origin="user", state=CONFIRMED_STATE)
    )
    for seed in seeds:
        graph.create_edge(
            EdgeCreate(
                source_id=seed.id,
                target_id=shared.id,
                type="references",
                origin="user",
                state=CONFIRMED_STATE,
            )
        )
    db_session.flush()

    service = GraphWorkspaceService(db_session, BOOTSTRAP_USER_ID)
    result = service.get_workspace(seed_limit=6, neighbor_limit=6, node_limit=4)
    assert len(result.nodes) <= 4
    assert result.truncated is True
