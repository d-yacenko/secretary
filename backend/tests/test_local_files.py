import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.db.models import Job, Object, Representation, User
from app.jobs.constants import JOB_TYPE_INGEST_LOCAL_FILE
from app.jobs.handlers import handle_ingest_local_file
from app.local.constants import (
    POLICY_INDEX_TEXT,
    POLICY_METADATA_ONLY,
    PROVIDER_LOCAL_DEVICE,
)
from app.local.paths import LocalPathResolver
from app.main import app
from app.services.dataset_tool_service import DatasetToolService
from app.services.job_queue_service import JobQueueService
from app.services.local_device_service import LocalDeviceService
from app.services.local_file_sync_service import LocalFileReport, LocalFileSyncService
from app.services.representation_service import KIND_SCHEMA, KIND_SAMPLE, KIND_STATISTICS
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def local_mirror(tmp_path: Path) -> Path:
    return tmp_path / "local-mirror"


@pytest.fixture
def local_client(db_session, local_mirror: Path):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with patch("app.core.config.settings.local_files_root", str(local_mirror)):
        with TestClient(app) as client:
            yield client
    app.dependency_overrides.clear()


def _device_service(db_session, local_mirror: Path) -> LocalDeviceService:
    return LocalDeviceService(
        db_session,
        BOOTSTRAP_USER_ID,
        LocalPathResolver(local_mirror),
    )


def _sync_service(db_session, local_mirror: Path, upload_root: Path) -> LocalFileSyncService:
    return LocalFileSyncService(
        db_session,
        BOOTSTRAP_USER_ID,
        LocalPathResolver(local_mirror),
        JobQueueService(db_session),
        upload_root=upload_root,
    )


def _mtime_iso(path: Path) -> str:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()


def test_register_device_and_root(local_mirror: Path, db_session) -> None:
    service = _device_service(db_session, local_mirror)
    device = service.register_device("laptop-1", "Work laptop")
    assert device.created
    root = service.register_root("laptop-1", "projects/alpha", default_policy=POLICY_METADATA_ONLY)
    assert root.created
    assert root.root_path == "projects/alpha"
    resolved = LocalPathResolver(local_mirror).resolve_root_path(
        BOOTSTRAP_USER_ID, "laptop-1", "projects/alpha"
    )
    assert resolved.is_dir()


def test_scan_registers_local_files_and_skips_unchanged_rescan(
    local_mirror: Path, db_session, tmp_path: Path
) -> None:
    upload_root = tmp_path / "uploads"
    device_service = _device_service(db_session, local_mirror)
    device_service.register_device("desk-1", "Desktop")
    root = device_service.register_root(
        "desk-1",
        "docs",
        default_policy=POLICY_INDEX_TEXT,
    )
    root_dir = LocalPathResolver(local_mirror).resolve_root_path(
        BOOTSTRAP_USER_ID, "desk-1", "docs"
    )
    note = root_dir / "notes.txt"
    note.write_text("local desktop notes content", encoding="utf-8")

    sync = _sync_service(db_session, local_mirror, upload_root)
    first = sync.scan_root(root.root_id)
    assert first.objects_created == 1
    assert first.ingest_jobs_enqueued == 1

    obj = db_session.scalar(
        select(Object).where(
            Object.user_id == BOOTSTRAP_USER_ID,
            Object.provider == PROVIDER_LOCAL_DEVICE,
        )
    )
    assert obj is not None
    assert obj.canonical_uri.startswith("personal://device/desk-1/file/")
    assert obj.metadata_["local_relative_path"] == "notes.txt"

    second = sync.scan_root(root.root_id)
    assert second.objects_unchanged == 1
    assert second.ingest_jobs_enqueued == 0


def test_large_csv_local_file_produces_schema_and_sample(
    local_mirror: Path, db_session, tmp_path: Path
) -> None:
    upload_root = tmp_path / "uploads"
    device_service = _device_service(db_session, local_mirror)
    device_service.register_device("desk-2", "Desktop")
    root = device_service.register_root(
        "desk-2",
        "data",
        default_policy=POLICY_INDEX_TEXT,
    )
    root_dir = LocalPathResolver(local_mirror).resolve_root_path(
        BOOTSTRAP_USER_ID, "desk-2", "data"
    )
    csv_path = root_dir / "metrics.csv"
    rows = ["id,value"] + [f"{index},{index * 10}" for index in range(80)]
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    sync = _sync_service(db_session, local_mirror, upload_root)
    result = sync.scan_root(root.root_id)
    assert result.objects_created == 1
    assert result.ingest_jobs_enqueued == 1

    job = db_session.scalar(
        select(Job).where(Job.type == JOB_TYPE_INGEST_LOCAL_FILE)
    )
    assert job is not None

    with patch("app.jobs.handlers.SessionLocal", lambda: db_session), patch.object(
        db_session, "close", lambda: None
    ), patch(
        "app.core.config.settings.local_files_root", str(local_mirror)
    ):
        handle_ingest_local_file(
            db_session,
            None,
            {"object_id": job.payload["object_id"]},
            BOOTSTRAP_USER_ID,
        )

    obj = db_session.scalar(select(Object).where(Object.kind == "dataset"))
    assert obj is not None
    reps = db_session.scalars(
        select(Representation).where(Representation.object_id == obj.id)
    ).all()
    kinds = {rep.kind for rep in reps}
    assert KIND_SCHEMA in kinds
    assert KIND_SAMPLE in kinds
    assert KIND_STATISTICS in kinds
    assert obj.canonical_uri.startswith("personal://device/desk-2/file/")


def test_dataset_tools_query_columns(local_mirror: Path, db_session, tmp_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    device_service = _device_service(db_session, local_mirror)
    device_service.register_device("desk-3", "Desktop")
    root = device_service.register_root("desk-3", "tables", default_policy=POLICY_METADATA_ONLY)
    root_dir = LocalPathResolver(local_mirror).resolve_root_path(
        BOOTSTRAP_USER_ID, "desk-3", "tables"
    )
    parquet_path = root_dir / "metrics.parquet"
    pq.write_table(pa.table({"name": ["a", "b", "c"], "value": [1, 2, 3]}), parquet_path)

    sync = _sync_service(db_session, local_mirror, upload_root)
    sync.report_files(
        "desk-3",
        "tables",
        [
            LocalFileReport(
                relative_path="metrics.parquet",
                size=parquet_path.stat().st_size,
                modified_at=_mtime_iso(parquet_path),
            )
        ],
    )
    obj = db_session.scalar(select(Object).where(Object.kind == "dataset"))
    assert obj is not None

    tools = DatasetToolService(
        db_session,
        BOOTSTRAP_USER_ID,
        LocalPathResolver(local_mirror),
        upload_root=upload_root,
    )
    schema = tools.get_schema(obj.id)
    assert "name" in schema["schema_text"]
    sample = tools.get_sample(obj.id, limit=2)
    assert sample["row_count_in_sample"] == 2
    stats = tools.get_basic_stats(obj.id)
    assert "rows:" in stats["statistics_text"]
    query = tools.query_columns(obj.id, ["name", "value"], limit=2)
    assert len(query["rows"]) == 2


def test_user_b_cannot_scan_or_read_other_user_root(
    local_mirror: Path, db_session, tmp_path: Path
) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    service_a = _device_service(db_session, local_mirror)
    service_a.register_device("shared-device", "Shared")
    root = service_a.register_root("shared-device", "private", default_policy=POLICY_METADATA_ONLY)

    service_b = LocalDeviceService(db_session, user_b_id, LocalPathResolver(local_mirror))
    from app.services.errors import NotFoundError

    with pytest.raises(NotFoundError):
        service_b.get_root_for_user(root.root_id)

    sync_b = LocalFileSyncService(
        db_session,
        user_b_id,
        LocalPathResolver(local_mirror),
        JobQueueService(db_session),
        upload_root=tmp_path / "uploads-b",
    )
    with pytest.raises(NotFoundError):
        sync_b.scan_root(root.root_id)


def test_worker_rejects_other_user_local_ingest_job(db_session, local_mirror: Path) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="document",
        title="secret.txt",
        origin="user",
        state="confirmed",
        provider=PROVIDER_LOCAL_DEVICE,
        external_id="device-a:secret.txt",
        metadata_={
            "device_key": "device-a",
            "local_root_path": "docs",
            "local_relative_path": "secret.txt",
        },
    )
    db_session.add(obj)
    db_session.flush()

    with patch("app.jobs.handlers.SessionLocal", lambda: db_session), patch.object(
        db_session, "close", lambda: None
    ):
        with pytest.raises(ValueError, match="ownership mismatch"):
            handle_ingest_local_file(
            db_session,
            None,
            {"object_id": str(obj.id)},
            user_b_id,
        )


def test_local_api_register_and_scan(local_client: TestClient, local_mirror: Path) -> None:
    device_resp = local_client.post(
        "/local/devices/register",
        json={"device_key": "api-device", "display_name": "API device"},
    )
    assert device_resp.status_code == 201

    root_resp = local_client.post(
        "/local/roots/register",
        json={
            "device_key": "api-device",
            "root_path": "workspace",
            "default_policy": POLICY_METADATA_ONLY,
        },
    )
    assert root_resp.status_code == 201
    root_id = root_resp.json()["root_id"]

    root_dir = LocalPathResolver(local_mirror).resolve_root_path(
        BOOTSTRAP_USER_ID, "api-device", "workspace"
    )
    (root_dir / "readme.md").write_text("# hello", encoding="utf-8")

    scan_resp = local_client.post(f"/local/roots/{root_id}/scan")
    assert scan_resp.status_code == 200
    body = scan_resp.json()
    assert body["objects_created"] == 1
    assert body["ingest_jobs_enqueued"] == 0
