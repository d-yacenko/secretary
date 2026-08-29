import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_db, get_embedding_service
from app.api.schemas import EdgeCreate, ObjectCreate, ResourceRegisterRequest
from app.db.models import Job, Object, Representation, User
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.llm.embedding_service import FakeEmbeddingService
from app.main import app
from app.resources.constants import PROVIDER_GOOGLE_DRIVE, PROVIDER_YANDEX_DISK
from app.resources.web_fetch import WebFetchResult
from app.services.graph_service import GraphService
from app.services.job_queue_service import JobQueueService
from app.services.resource_registration_service import ResourceRegistrationService
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_embedding() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def user_b_id(db_session):
    user_id = uuid4()
    db_session.add(User(id=user_id, display_name="User B"))
    db_session.flush()
    return user_id


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


def _register_service(
    db_session,
    fake_embedding: FakeEmbeddingService,
    upload_root: Path,
) -> ResourceRegistrationService:
    return ResourceRegistrationService(
        session=db_session,
        user_id=BOOTSTRAP_USER_ID,
        job_queue=JobQueueService(db_session),
        embedding_service=fake_embedding,
        upload_root=upload_root,
    )


def test_register_google_drive_metadata_only_no_embed_job(
    db_session, fake_embedding, upload_root
) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Budget report",
            canonical_uri="https://drive.google.com/file/d/abc123/view",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="abc123",
            metadata={
                "mime_type": "application/pdf",
                "size": 1024,
                "modified_at": "2026-01-15T10:00:00Z",
                "etag": "rev-1",
            },
        )
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 0
    assert result.representations_created == 0

    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj is not None
    assert obj.provider == PROVIDER_GOOGLE_DRIVE
    assert obj.external_id == "abc123"
    assert obj.canonical_uri == "https://drive.google.com/file/d/abc123/view"
    assert obj.metadata_["mime_type"] == "application/pdf"


def test_register_same_revision_skips_reprocessing(
    db_session, fake_embedding, upload_root
) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    payload = ResourceRegisterRequest(
        kind="file",
        title="Budget report",
        canonical_uri="https://drive.google.com/file/d/abc123/view",
        provider=PROVIDER_GOOGLE_DRIVE,
        external_id="abc123",
        metadata={
            "mime_type": "application/pdf",
            "etag": "rev-1",
            "modified_at": "2026-01-15T10:00:00Z",
        },
    )
    first = service.register(payload)
    second = service.register(payload)
    assert first.status == "created"
    assert second.status == "unchanged"
    assert second.jobs_enqueued == 0

    job_count = db_session.scalar(
        select(func.count()).select_from(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)
    )
    assert job_count == 0


def test_register_revision_change_updates_metadata_without_embed(
    db_session, fake_embedding, upload_root
) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    first = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Budget report",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="abc123",
            canonical_uri="https://drive.google.com/file/d/abc123/view",
            metadata={"etag": "rev-1", "modified_at": "2026-01-15T10:00:00Z"},
        )
    )
    second = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Budget report v2",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="abc123",
            canonical_uri="https://drive.google.com/file/d/abc123/view",
            metadata={"etag": "rev-2", "modified_at": "2026-02-01T10:00:00Z"},
        )
    )
    assert second.status == "updated"
    assert second.jobs_enqueued == 0
    obj = db_session.scalar(select(Object).where(Object.id == first.object_id))
    assert obj.title == "Budget report v2"
    assert obj.metadata_["etag"] == "rev-2"


def test_register_yandex_disk_metadata(db_session, fake_embedding, upload_root) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Shared doc",
            canonical_uri="https://disk.yandex.ru/client/disk/doc",
            provider=PROVIDER_YANDEX_DISK,
            external_id="disk-file-9",
            metadata={
                "mime_type": "text/plain",
                "size": 200,
                "modified_at": "2026-03-01T12:00:00Z",
                "revision": "42",
            },
        )
    )
    assert result.status == "created"
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.provider == PROVIDER_YANDEX_DISK


def test_register_text_with_ingest_creates_representations_and_job(
    db_session, fake_embedding, upload_root
) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    text = "Important meeting notes for the project."
    result = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Meeting notes",
            text=text,
            ingest_content=True,
        )
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 1
    assert result.representations_created == 1

    reps = list(
        db_session.scalars(
            select(Representation).where(Representation.object_id == result.object_id)
        ).all()
    )
    assert len(reps) == 1


def test_register_web_page_stub_without_ingest(
    db_session, fake_embedding, upload_root
) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="web_page",
            title="Example",
            canonical_uri="https://example.com/docs",
        )
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 0
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.kind == "web_page"
    assert obj.canonical_uri == "https://example.com/docs"


@patch("app.services.resource_registration_service.fetch_web_page")
def test_register_web_page_with_ingest(
    mock_fetch, db_session, fake_embedding, upload_root
) -> None:
    mock_fetch.return_value = WebFetchResult(
        title="Fetched title",
        text="Bounded page text",
        final_url="https://example.com/docs",
    )
    service = _register_service(db_session, fake_embedding, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="web_page",
            title="Example",
            canonical_uri="https://example.com/docs",
            ingest_content=True,
        )
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 1
    assert result.representations_created == 1
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.title == "Fetched title"
    assert obj.body == "Bounded page text"


def test_register_upload_file_with_ingest(
    db_session, fake_embedding, upload_root, tmp_path
) -> None:
    source = tmp_path / "notes.md"
    source.write_text("Uploaded markdown content.", encoding="utf-8")
    service = _register_service(db_session, fake_embedding, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Uploaded notes",
            ingest_content=True,
            metadata={"content_hash": "hash-notes-1"},
        ),
        uploaded_path=source,
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 1
    assert result.representations_created == 1
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.provider == "upload"
    assert obj.external_id == "hash-notes-1"


def test_task_can_link_to_registered_resource(db_session, fake_embedding, upload_root) -> None:
    service = _register_service(db_session, fake_embedding, upload_root)
    registered = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Drive spec",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="spec-1",
            canonical_uri="https://drive.google.com/file/d/spec-1/view",
            metadata={"etag": "e1"},
        )
    )
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    task = graph.create_object(
        ObjectCreate(kind="task", title="Review spec", origin="user")
    )
    edge = graph.create_edge(
        EdgeCreate(
            source_id=task.id,
            target_id=registered.object_id,
            type="attached_to",
            origin="user",
            state="confirmed",
        )
    )
    assert edge.source_id == task.id
    assert edge.target_id == registered.object_id


def test_register_api_json(client: TestClient) -> None:
    response = client.post(
        "/resources/register",
        json={
            "kind": "file",
            "title": "API file",
            "canonical_uri": "https://drive.google.com/file/d/api-1/view",
            "provider": PROVIDER_GOOGLE_DRIVE,
            "external_id": "api-1",
            "metadata": {"etag": "api-e1", "mime_type": "text/plain"},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["jobs_enqueued"] == 0


def test_register_api_multipart_upload(client: TestClient, upload_root: Path) -> None:
    payload = {
        "kind": "document",
        "title": "Multipart doc",
        "ingest_content": True,
        "metadata": {"content_hash": "multipart-1"},
    }
    response = client.post(
        "/resources/register",
        data={"payload": json.dumps(payload)},
        files={"file": ("note.txt", b"hello from upload", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["representations_created"] == 1
    assert body["jobs_enqueued"] == 1


def test_user_b_cannot_access_user_a_registered_resource(
    db_session, fake_embedding, upload_root, user_b_id
) -> None:
    service_a = ResourceRegistrationService(
        db_session,
        BOOTSTRAP_USER_ID,
        JobQueueService(db_session),
        embedding_service=fake_embedding,
        upload_root=upload_root,
    )
    result = service_a.register(
        ResourceRegisterRequest(
            kind="document",
            title="Private doc",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="private-1",
            metadata={"etag": "p1"},
        )
    )
    service_b = ResourceRegistrationService(
        db_session,
        user_b_id,
        JobQueueService(db_session),
        embedding_service=fake_embedding,
        upload_root=upload_root,
    )
    from app.services.errors import NotFoundError

    with pytest.raises(NotFoundError):
        service_b.get_object_for_user(result.object_id)
