import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_embedding_service
from app.api.schemas import ObjectCreate
from app.llm.embedding_service import FakeEmbeddingService
from app.main import app
from app.services.graph_service import GraphService
from app.services.search_service import SearchService


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


def test_semantic_search_finds_different_wording(db_session, fake_embedding_service) -> None:
    graph = GraphService(db_session, fake_embedding_service)
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Quarterly budget planning meeting",
            body="Discuss revenue targets and expense review.",
            origin="test",
        )
    )
    graph.create_object(
        ObjectCreate(
            kind="note",
            title="Weekend hiking trip",
            body="Mountain trail and camping gear.",
            origin="test",
        )
    )

    search = SearchService(db_session, fake_embedding_service)
    results = search.search("budget expense quarterly review")

    assert len(results) >= 1
    assert results[0].title == "Quarterly budget planning meeting"


def test_search_project_id_graph_filter(db_session, fake_embedding_service) -> None:
    graph = GraphService(db_session, fake_embedding_service)
    project = graph.create_object(ObjectCreate(kind="project", title="Alpha", origin="test"))
    task = graph.create_object(ObjectCreate(kind="task", title="Alpha task", origin="test"))
    other = graph.create_object(ObjectCreate(kind="task", title="Other task", origin="test"))

    from app.api.schemas import EdgeCreate

    graph.create_edge(
        EdgeCreate(
            source_id=project.id,
            target_id=task.id,
            type="parent_of",
            origin="test",
            state="observed",
        )
    )

    search = SearchService(db_session, fake_embedding_service)
    results = search.search("task", project_id=project.id, limit=10)
    titles = {item.title for item in results}
    assert "Alpha task" in titles
    assert "Other task" not in titles


def test_search_endpoint(client) -> None:
    client.post(
        "/objects",
        json={
            "kind": "note",
            "title": "Renewable solar energy roadmap",
            "origin": "test",
        },
    )
    response = client.get("/search", params={"q": "solar energy roadmap"})
    assert response.status_code == 200
    assert len(response.json()) >= 1
