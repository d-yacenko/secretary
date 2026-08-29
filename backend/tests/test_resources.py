import hashlib
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
from app.resources.constants import (
    CONTENT_INGESTED_REVISION_KEY,
    MAX_UPLOAD_BYTES,
    PROVIDER_GOOGLE_DRIVE,
    PROVIDER_YANDEX_DISK,
)
from app.resources.upload_staging import StagedUpload
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
def upload_root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


def _register_service(db_session, upload_root: Path) -> ResourceRegistrationService:
    return ResourceRegistrationService(
        session=db_session,
        user_id=BOOTSTRAP_USER_ID,
        job_queue=JobQueueService(db_session),
        upload_root=upload_root,
    )


def _staged_upload(path: Path, filename: str | None = None) -> StagedUpload:
    data = path.read_bytes()
    return StagedUpload(
        path=path,
        content_hash=hashlib.sha256(data).hexdigest(),
        original_filename=filename or path.name,
        size=len(data),
    )


def test_register_google_drive_metadata_only_no_embed_job(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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


def test_register_same_revision_skips_reprocessing(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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


def test_register_same_revision_metadata_change_no_reingest(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
    base_metadata = {
        "etag": "rev-1",
        "modified_at": "2026-01-15T10:00:00Z",
        "mime_type": "application/pdf",
    }
    first = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Budget report",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="abc123",
            canonical_uri="https://drive.google.com/file/d/abc123/view",
            metadata=base_metadata,
            ingest_content=True,
            text="version one body",
        )
    )
    assert first.jobs_enqueued == 1

    second = service.register(
        ResourceRegisterRequest(
            kind="file",
            title="Budget report renamed",
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="abc123",
            canonical_uri="https://drive.google.com/file/d/abc123/new-view",
            metadata={**base_metadata, "mime_type": "application/vnd.pdf"},
            ingest_content=True,
            text="version one body",
        )
    )
    assert second.status == "updated"
    assert second.jobs_enqueued == 0
    assert second.representations_created == 0

    obj = db_session.scalar(select(Object).where(Object.id == first.object_id))
    assert obj.title == "Budget report renamed"
    assert obj.metadata_[CONTENT_INGESTED_REVISION_KEY] is not None

    job_count = db_session.scalar(
        select(func.count()).select_from(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)
    )
    assert job_count == 1


def test_register_same_revision_already_ingested_skips_content(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
    metadata = {"etag": "rev-1", "modified_at": "2026-01-15T10:00:00Z"}
    first = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Notes",
            text="stable notes",
            ingest_content=True,
            metadata=metadata,
        )
    )
    assert first.jobs_enqueued == 1

    with patch("app.services.resource_registration_service.fetch_web_page") as mock_fetch:
        second = service.register(
            ResourceRegisterRequest(
                kind="document",
                title="Notes",
                text="stable notes",
                ingest_content=True,
                metadata=metadata,
            )
        )
        mock_fetch.assert_not_called()

    assert second.status == "unchanged"
    assert second.jobs_enqueued == 0
    assert second.representations_created == 0


def test_register_metadata_only_then_ingest_once(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
    metadata = {"etag": "rev-ingest-1", "modified_at": "2026-02-01T10:00:00Z"}
    first = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Deferred ingest",
            text="content to ingest later",
            metadata=metadata,
        )
    )
    assert first.jobs_enqueued == 0
    obj = db_session.scalar(select(Object).where(Object.id == first.object_id))
    assert obj.metadata_.get(CONTENT_INGESTED_REVISION_KEY) is None

    second = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Deferred ingest",
            text="content to ingest later",
            ingest_content=True,
            metadata=metadata,
        )
    )
    assert second.status == "updated"
    assert second.jobs_enqueued == 1
    assert second.representations_created == 1
    obj = db_session.scalar(select(Object).where(Object.id == first.object_id))
    assert obj.metadata_[CONTENT_INGESTED_REVISION_KEY] == obj.metadata_["content_revision"]

    third = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Deferred ingest",
            text="content to ingest later",
            ingest_content=True,
            metadata=metadata,
        )
    )
    assert third.jobs_enqueued == 0


def test_register_new_revision_ingests_when_requested(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
    first = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Evolving doc",
            text="revision one",
            ingest_content=True,
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="evolving-doc-1",
            metadata={"etag": "rev-a", "modified_at": "2026-01-01T10:00:00Z"},
        )
    )
    second = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Evolving doc",
            text="revision two",
            ingest_content=True,
            provider=PROVIDER_GOOGLE_DRIVE,
            external_id="evolving-doc-1",
            metadata={"etag": "rev-b", "modified_at": "2026-02-01T10:00:00Z"},
        )
    )
    assert second.status == "updated"
    assert second.jobs_enqueued == 1
    assert second.representations_created == 1

    job_count = db_session.scalar(
        select(func.count()).select_from(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)
    )
    assert job_count == 2


def test_register_revision_change_updates_metadata_without_embed(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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


def test_register_yandex_disk_metadata(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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
    db_session, upload_root
) -> None:
    service = _register_service(db_session, upload_root)
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


@patch("app.services.embedding_index.refresh_object_embedding")
def test_register_changed_resource_one_embed_job_no_sync_embedding(
    mock_refresh, db_session, upload_root
) -> None:
    service = _register_service(db_session, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Embed once",
            text="unique content for embedding",
            ingest_content=True,
        )
    )
    mock_refresh.assert_not_called()
    assert result.jobs_enqueued == 1
    job_count = db_session.scalar(
        select(func.count()).select_from(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)
    )
    assert job_count == 1


def test_register_unchanged_ingested_revision_no_embedding_activity(
    db_session, upload_root
) -> None:
    service = _register_service(db_session, upload_root)
    metadata = {"etag": "stable", "modified_at": "2026-01-01T00:00:00Z"}
    first = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Stable",
            text="same",
            ingest_content=True,
            metadata=metadata,
        )
    )
    rep_count_before = db_session.scalar(
        select(func.count()).select_from(Representation).where(
            Representation.object_id == first.object_id
        )
    )

    with patch("app.services.embedding_index.refresh_object_embedding") as mock_refresh:
        second = service.register(
            ResourceRegisterRequest(
                kind="document",
                title="Stable",
                text="same",
                ingest_content=True,
                metadata=metadata,
            )
        )
        mock_refresh.assert_not_called()

    assert second.jobs_enqueued == 0
    rep_count_after = db_session.scalar(
        select(func.count()).select_from(Representation).where(
            Representation.object_id == first.object_id
        )
    )
    assert rep_count_after == rep_count_before


def test_register_web_page_stub_without_ingest(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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


@patch("app.services.resource_registration_service.fetch_web_page")
def test_register_web_page_with_ingest(mock_fetch, db_session, upload_root) -> None:
    mock_fetch.return_value = WebFetchResult(
        title="Fetched title",
        text="Bounded page text",
        final_url="https://example.com/docs",
    )
    service = _register_service(db_session, upload_root)
    tx_checks: list[bool] = []

    def fetch_with_tx_check(url: str) -> WebFetchResult:
        tx_checks.append(db_session.in_transaction())
        return mock_fetch.return_value

    mock_fetch.side_effect = fetch_with_tx_check

    result = service.register(
        ResourceRegisterRequest(
            kind="web_page",
            title="Example",
            canonical_uri="https://example.com/docs",
            ingest_content=True,
        )
    )
    assert tx_checks == [False]
    assert result.status == "created"
    assert result.jobs_enqueued == 1
    assert result.representations_created == 1
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.title == "Fetched title"
    assert obj.body == "Bounded page text"


def test_register_upload_file_with_ingest(db_session, upload_root, tmp_path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("Uploaded markdown content.", encoding="utf-8")
    staged = _staged_upload(source, "notes.md")
    service = _register_service(db_session, upload_root)
    result = service.register(
        ResourceRegisterRequest(
            kind="document",
            title="Uploaded notes",
            ingest_content=True,
        ),
        staged_upload=staged,
    )
    assert result.status == "created"
    assert result.jobs_enqueued == 1
    assert result.representations_created == 1
    obj = db_session.scalar(select(Object).where(Object.id == result.object_id))
    assert obj.provider == "upload"
    assert obj.external_id == staged.content_hash
    assert obj.metadata_["upload_filename"] == "notes.md"


def test_task_can_link_to_registered_resource(db_session, upload_root) -> None:
    service = _register_service(db_session, upload_root)
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


def test_register_api_multipart_upload(client: TestClient) -> None:
    content = b"hello from upload"
    content_hash = hashlib.sha256(content).hexdigest()
    payload = {
        "kind": "document",
        "title": "Multipart doc",
        "ingest_content": True,
    }
    response = client.post(
        "/resources/register",
        data={"payload": json.dumps(payload)},
        files={"file": ("note.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["representations_created"] == 1
    assert body["jobs_enqueued"] == 1
    assert body["external_id"] == content_hash


def test_register_api_upload_at_limit(client: TestClient) -> None:
    with patch("app.resources.upload_staging.MAX_UPLOAD_BYTES", 1024):
        content = b"x" * 1024
        response = client.post(
            "/resources/register",
            data={"payload": json.dumps({"kind": "document", "title": "Limit ok"})},
            files={"file": ("limit.txt", content, "text/plain")},
        )
    assert response.status_code == 201


def test_register_api_upload_over_limit_rejected(client: TestClient) -> None:
    with patch("app.resources.upload_staging.MAX_UPLOAD_BYTES", 1024):
        content = b"x" * 1025
        response = client.post(
            "/resources/register",
            data={"payload": json.dumps({"kind": "document", "title": "Too big"})},
            files={"file": ("big.txt", content, "text/plain")},
        )
    assert response.status_code == 413


def test_register_api_preserves_original_filename(client: TestClient, db_session) -> None:
    content = b"filename test"
    response = client.post(
        "/resources/register",
        data={"payload": json.dumps({"kind": "document", "title": "Named upload"})},
        files={"file": ("My Report.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    obj = db_session.scalar(select(Object).where(Object.id == response.json()["object_id"]))
    assert obj.metadata_["upload_filename"] == "My_Report.txt"


def test_register_api_malformed_payload_returns_422(client: TestClient) -> None:
    response = client.post(
        "/resources/register",
        data={"payload": "not-json"},
        files={"file": ("note.txt", b"hi", "text/plain")},
    )
    assert response.status_code == 422

    bad_json = client.post(
        "/resources/register",
        content=b"{bad",
        headers={"content-type": "application/json"},
    )
    assert bad_json.status_code == 422


def test_user_b_cannot_access_user_a_registered_resource(
    db_session, upload_root, user_b_id
) -> None:
    service_a = ResourceRegistrationService(
        db_session,
        BOOTSTRAP_USER_ID,
        JobQueueService(db_session),
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
        upload_root=upload_root,
    )
    from app.services.errors import NotFoundError

    with pytest.raises(NotFoundError):
        service_b.get_object_for_user(result.object_id)


@pytest.fixture
def user_b_id(db_session):
    user_id = uuid4()
    db_session.add(User(id=user_id, display_name="User B"))
    db_session.flush()
    return user_id
