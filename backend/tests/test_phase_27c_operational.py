import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.connectors.google.constants import (
    CALENDAR_READONLY_SCOPE,
    DRIVE_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.drive_normalize import build_canonical_uri
from app.connectors.google.drive_sync import build_drive_sync_service
from app.connectors.google.drive_transport import DriveFilesPage
from app.connectors.google.encryption import CredentialEncryption
from app.db.engine import engine
from app.db.models import GoogleAccount, Job, Object, User
from app.jobs.constants import (
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_DRIVE,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
)
from app.jobs.handlers import HANDLERS
from app.jobs.worker import process_one_job
from app.main import app
from app.services.job_queue_service import utcnow
from app.services.open_target_service import OpenTargetService
from app.services.source_sync_scheduler import SourceSyncScheduler
from app.users.bootstrap import BOOTSTRAP_USER_ID

ACCESS_TOKEN = "google-access-token-ya29.fake"
REFRESH_TOKEN = "google-refresh-token"


@pytest.fixture(autouse=True)
def cleanup_google_drive_jobs() -> None:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    session.execute(delete(Job).where(Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE))
    trans.commit()
    conn.close()
    yield


@pytest.fixture
def credential_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def oauth_client_file(tmp_path: Path) -> str:
    path = tmp_path / "google-oauth-client.json"
    path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def google_drive_settings(monkeypatch: pytest.MonkeyPatch, credential_key: str) -> None:
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)
    monkeypatch.setattr(
        "app.core.config.settings.source_sync_google_drive_interval_seconds",
        300,
    )


def _google_account(
    db_session,
    credential_key: str,
    scopes: list[str],
    user_id: uuid.UUID = BOOTSTRAP_USER_ID,
    email: str = "user@example.com",
) -> GoogleAccount:
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_tokens(
        user_id=user_id,
        email=email,
        scopes=scopes,
        access_token=ACCESS_TOKEN,
        refresh_token=REFRESH_TOKEN,
        token_expiry=utcnow() + timedelta(hours=1),
    )
    db_session.commit()
    return account


def _persist_google_drive_schedule(
    credential_key: str,
    scopes: list[str],
    user_id: uuid.UUID = BOOTSTRAP_USER_ID,
) -> GoogleAccount:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    store = GoogleAccountStore(session, CredentialEncryption(credential_key))
    account = store.upsert_tokens(
        user_id=user_id,
        email="user@example.com",
        scopes=scopes,
        access_token=ACCESS_TOKEN,
        refresh_token=REFRESH_TOKEN,
        token_expiry=utcnow() + timedelta(hours=1),
    )
    SourceSyncScheduler(session).run_maintenance()
    trans.commit()
    conn.close()
    return account


class _FakeDriveTransport:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_start_page_token(self, access_token: str) -> str:
        return "start-token"

    def list_files(self, access_token: str, page_token: str | None, page_size: int) -> DriveFilesPage:
        self.calls.append(("list_files", page_token, page_size))
        return DriveFilesPage(files=[], next_page_token=None)

    def list_changes(self, access_token: str, page_token: str, page_size: int):
        raise NotImplementedError

    def close(self) -> None:
        pass


def test_drive_scope_ensures_single_recurring_row(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    scopes = [GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE]
    account = _google_account(db_session, credential_key, scopes)
    scheduler = SourceSyncScheduler(db_session)
    scheduler.run_maintenance()
    scheduler.run_maintenance()
    db_session.commit()
    jobs = list(
        db_session.scalars(
            select(Job).where(
                Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE,
                Job.user_id == BOOTSTRAP_USER_ID,
            )
        )
    )
    assert len(jobs) == 1
    assert jobs[0].payload == {"account_id": str(account.id)}


def test_no_drive_scope_skips_drive_recurring_row(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    _google_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE],
    )
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()
    count = db_session.scalar(
        select(func.count()).select_from(Job).where(Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE)
    )
    assert count == 0


def test_gmail_calendar_rows_remain_with_drive_scope(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    scopes = [GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE]
    account = _google_account(db_session, credential_key, scopes)
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()
    gmail = db_session.scalar(
        select(Job).where(
            Job.type == JOB_TYPE_SYNC_GOOGLE_GMAIL,
            Job.payload["account_id"].as_string() == str(account.id),
        )
    )
    calendar = db_session.scalar(
        select(Job).where(
            Job.type == JOB_TYPE_SYNC_GOOGLE_CALENDAR,
            Job.payload["account_id"].as_string() == str(account.id),
        )
    )
    assert gmail is not None
    assert calendar is not None


def test_trigger_all_for_user_includes_google_drive(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account = _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
    )
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()
    triggered = SourceSyncScheduler(db_session).trigger_all_for_user(BOOTSTRAP_USER_ID)
    assert any(item == f"google_drive:{account.id}" for item in triggered)


def test_cross_user_cannot_trigger_google_drive_jobs(
    db_session,
    credential_key: str,
    issue_bearer,
    google_drive_settings,
) -> None:
    other_user_id = uuid.uuid4()
    db_session.add(User(id=other_user_id, display_name="Other"))
    db_session.flush()
    other_account = _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
        user_id=other_user_id,
        email="other@example.com",
    )
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()
    triggered = SourceSyncScheduler(db_session).trigger_all_for_user(BOOTSTRAP_USER_ID)
    assert f"google_drive:{other_account.id}" not in triggered


def test_drive_recurring_success_reschedules_same_row(
    credential_key: str,
    google_drive_settings,
    fake_embedding_service,
) -> None:
    scopes = [DRIVE_READONLY_SCOPE]
    account = _persist_google_drive_schedule(credential_key, scopes)
    conn = engine.connect()
    session = Session(bind=conn)
    job = session.scalar(
        select(Job).where(
            Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE,
            Job.payload["account_id"].as_string() == str(account.id),
        )
    )
    job_id = job.id
    conn.close()

    with patch.dict(HANDLERS, {JOB_TYPE_SYNC_GOOGLE_DRIVE: lambda s, e, p, u: None}):
        assert process_one_job(fake_embedding_service)

    conn = engine.connect()
    session = Session(bind=conn)
    job = session.get(Job, job_id)
    assert job.status == JOB_STATUS_PENDING
    assert job.attempts == 0
    assert job.last_error is None
    assert "last_success_at" in job.payload
    assert job.run_after > utcnow()
    assert job.run_after <= utcnow() + timedelta(seconds=305)
    conn.close()


def test_drive_failed_recurring_job_rearms(
    credential_key: str,
    google_drive_settings,
    fake_embedding_service,
) -> None:
    account = _persist_google_drive_schedule(credential_key, [DRIVE_READONLY_SCOPE])
    conn = engine.connect()
    session = Session(bind=conn)
    job = session.scalar(
        select(Job).where(
            Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE,
            Job.payload["account_id"].as_string() == str(account.id),
        )
    )
    job_id = job.id
    conn.close()

    def failing_handler(session, embedding, payload, user_id):
        raise RuntimeError("drive sync failed")

    with patch.dict(HANDLERS, {JOB_TYPE_SYNC_GOOGLE_DRIVE: failing_handler}):
        assert process_one_job(fake_embedding_service)

    conn = engine.connect()
    session = Session(bind=conn)
    job = session.get(Job, job_id)
    job.attempts = 3
    job.status = JOB_STATUS_FAILED
    job.run_after = utcnow() - timedelta(seconds=1)
    job.last_error = "RuntimeError"
    session.commit()
    SourceSyncScheduler(session).run_maintenance()
    session.commit()
    job = session.get(Job, job_id)
    assert job.status == JOB_STATUS_PENDING
    assert job.attempts == 0
    conn.close()


def test_sources_status_includes_google_drive_without_secrets(
    db_session,
    credential_key: str,
    google_drive_settings,
    auth_headers,
) -> None:
    from tests.conftest import AuthTestClient

    _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
        email="drive@example.com",
    )
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as raw:
        client = AuthTestClient(raw, auth_headers)
        response = client.get("/sources/status")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    drive_rows = [row for row in body["sources"] if row["provider"] == "google_drive"]
    assert any(row["account_label"] == "drive@example.com" for row in drive_rows)
    dumped = json.dumps(body)
    assert ACCESS_TOKEN not in dumped
    assert REFRESH_TOKEN not in dumped
    assert "changes_page_token" not in dumped


def test_drive_job_payload_contains_only_account_id(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account = _google_account(db_session, credential_key, scopes=[DRIVE_READONLY_SCOPE])
    SourceSyncScheduler(db_session).run_maintenance()
    db_session.commit()
    job = db_session.scalar(select(Job).where(Job.type == JOB_TYPE_SYNC_GOOGLE_DRIVE))
    assert job is not None
    assert set(job.payload.keys()) == {"account_id"}
    assert job.payload["account_id"] == str(account.id)


def test_drive_worker_handler_calls_sync_with_account_id_and_user_id(
    db_session,
    credential_key: str,
    google_drive_settings,
    oauth_client_file,
) -> None:
    account = _google_account(db_session, credential_key, scopes=[DRIVE_READONLY_SCOPE])
    transport = _FakeDriveTransport()
    service = build_drive_sync_service(
        session=db_session,
        credential_key=credential_key,
        client_file=oauth_client_file,
        redirect_uri="http://localhost:18080/auth/google/callback",
        max_items_per_run=500,
        http_client=None,
    )
    service._transport = transport

    with patch(
        "app.jobs.source_sync_handlers._google_drive_sync_service",
        return_value=service,
    ):
        from app.jobs.source_sync_handlers import handle_sync_google_drive

        handle_sync_google_drive(
            db_session,
            None,
            {"account_id": str(account.id)},
            BOOTSTRAP_USER_ID,
        )
    assert transport.calls


def test_open_target_valid_google_drive_object(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account = _google_account(db_session, credential_key, scopes=[DRIVE_READONLY_SCOPE])
    file_id = "drive-file-valid"
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider="google_drive",
        external_id=file_id,
        origin="source",
        state="observed",
        title="Drive doc",
        metadata_={"account_id": str(account.id), "file_id": file_id},
        canonical_uri="https://evil.example/phish",
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is True
    assert target.action == "web_url"
    assert target.label == "Открыть в Google Drive"
    assert target.url == build_canonical_uri(file_id)
    assert "evil.example" not in (target.url or "")


def test_open_target_ignores_malicious_web_view_link(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account = _google_account(db_session, credential_key, scopes=[DRIVE_READONLY_SCOPE])
    file_id = "drive-file-safe"
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider="google_drive",
        external_id=file_id,
        origin="source",
        state="observed",
        title="Safe",
        metadata_={
            "account_id": str(account.id),
            "file_id": file_id,
            "web_view_link": "https://evil.example/phish",
        },
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is True
    assert target.url == build_canonical_uri(file_id)


def test_open_target_cross_user_google_account_rejected(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    other_user = uuid.uuid4()
    db_session.add(User(id=other_user, display_name="Other"))
    db_session.flush()
    other_account = _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
        user_id=other_user,
        email="other@example.com",
    )
    file_id = "cross-user-file"
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider="google_drive",
        external_id=file_id,
        origin="source",
        state="observed",
        title="Cross user",
        metadata_={"account_id": str(other_account.id), "file_id": file_id},
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is False
    assert target.reason == "google_drive_metadata_tampered"


def test_open_target_external_id_mismatch_rejected(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account = _google_account(db_session, credential_key, scopes=[DRIVE_READONLY_SCOPE])
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider="google_drive",
        external_id="object-id",
        origin="source",
        state="observed",
        title="Mismatch",
        metadata_={"account_id": str(account.id), "file_id": "metadata-id"},
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is False
    assert target.reason == "google_drive_metadata_tampered"


def test_open_target_malformed_account_id_rejected(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    file_id = "malformed-account"
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="folder",
        provider="google_drive",
        external_id=file_id,
        origin="source",
        state="observed",
        title="Folder",
        metadata_={"account_id": "not-a-uuid", "file_id": file_id},
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is False
    assert target.reason == "google_drive_metadata_tampered"


def test_open_target_same_user_wrong_account_still_uses_file_id_only(
    db_session,
    credential_key: str,
    google_drive_settings,
) -> None:
    account_a = _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
        email="a@example.com",
    )
    account_b = _google_account(
        db_session,
        credential_key,
        scopes=[DRIVE_READONLY_SCOPE],
        email="b@example.com",
    )
    file_id = "shared-file-id"
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider="google_drive",
        external_id=file_id,
        origin="source",
        state="observed",
        title="Wrong account metadata",
        metadata_={"account_id": str(account_b.id), "file_id": file_id},
    )
    db_session.add(obj)
    db_session.commit()

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(obj.id)
    assert target.available is True
    assert target.url == f"https://drive.google.com/open?id={quote(file_id, safe='')}"
    assert str(account_a.id) != str(account_b.id)
