import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_embedding_service
from app.api.schemas import ObjectCreate
from app.llm.embedding_service import FakeEmbeddingService
from app.main import app
from app.services.graph_service import GraphService
from app.services.search_service import SearchService
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def fake_embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def client(db_session, fake_embedding_service):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_semantic_search_with_concept_stub_finds_different_wording(db_session) -> None:
    from app.llm.concept_stub_embedding import ConceptStubEmbeddingService

    stub = ConceptStubEmbeddingService()
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, stub)
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Prepare financial forecast for next quarter",
            origin="system",
        )
    )
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Weekend hiking trail guide",
            origin="system",
        )
    )

    search = SearchService(db_session, BOOTSTRAP_USER_ID, stub)
    results = search.search("future revenue planning")

    assert len(results) >= 1
    assert results[0].title == "Prepare financial forecast for next quarter"


def test_semantic_search_finds_different_wording(db_session, fake_embedding_service) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Quarterly budget planning meeting",
            body="Discuss revenue targets and expense review.",
            origin="system",
        )
    )
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Weekend hiking trip",
            body="Mountain trail and camping gear.",
            origin="system",
        )
    )

    search = SearchService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    results = search.search("budget expense quarterly review")

    assert len(results) >= 1
    assert results[0].title == "Quarterly budget planning meeting"


def test_search_project_id_graph_filter(db_session, fake_embedding_service) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    project = graph.create_object(ObjectCreate(kind="project", title="Alpha", origin="system"))
    task = graph.create_object(ObjectCreate(kind="task", title="Alpha task", origin="system"))
    other = graph.create_object(ObjectCreate(kind="task", title="Other task", origin="system"))

    from app.api.schemas import EdgeCreate

    graph.create_edge(
        EdgeCreate(
            source_id=project.id,
            target_id=task.id,
            type="parent_of",
            origin="system",
            state="observed",
        )
    )

    search = SearchService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    results = search.search("task", project_id=project.id, limit=10)
    titles = {item.title for item in results}
    assert "Alpha task" in titles
    assert "Other task" not in titles


def test_search_excludes_deleted_objects_by_default(
    db_session, fake_embedding_service
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    active = graph.create_object(
        ObjectCreate(
            kind="note",
            title="Active searchable calendar note",
            body="visible keyword marker",
            origin="system",
        )
    )
    tombstone = graph.create_object(
        ObjectCreate(
            kind="note",
            title="Deleted searchable calendar note",
            body="visible keyword marker tombstone",
            origin="system",
        )
    )
    tombstone.status = "deleted"
    db_session.flush()

    search = SearchService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)
    results = search.search("visible keyword marker")
    ids = {item.id for item in results}
    assert active.id in ids
    assert tombstone.id not in ids

    direct = graph.get_object(tombstone.id)
    assert direct.id == tombstone.id


def test_search_endpoint(client) -> None:
    client.post(
        "/objects",
        json={
            "kind": "note",
            "title": "Renewable solar energy roadmap",
            "origin": "system",
        },
    )
    response = client.get("/search", params={"q": "solar energy roadmap"})
    assert response.status_code == 200
    assert len(response.json()) >= 1
