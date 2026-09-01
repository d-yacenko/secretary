import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.connectors.google.constants import (
    CALENDAR_READONLY_SCOPE,
    DRIVE_API_BASE,
    DRIVE_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
    GOOGLE_DRIVE_FOLDER_MIME,
    GOOGLE_DRIVE_PROVIDER,
    GOOGLE_OAUTH_SCOPES,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.drive_normalize import build_canonical_uri, normalize_drive_file
from app.connectors.google.drive_sync import DriveSyncService, normalize_drive_sync_state
from app.connectors.google.drive_transport import DriveChangesPage, DriveFilesPage, DriveTransport
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.google.errors import GoogleApiError, GoogleConnectorError
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.db.models import GoogleAccount, Job, Object, User
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.main import app
from app.services.connection_status_service import ConnectionStatusService
from app.services.job_queue_service import JobQueueService
from app.users.bootstrap import BOOTSTRAP_USER_ID

ACCESS_TOKEN = "google-access-token-ya29.fake"
REFRESH_TOKEN = "google-refresh-token"


def utcnow() -> datetime:
    return datetime.now(UTC)


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
def google_settings(monkeypatch: pytest.MonkeyPatch, oauth_client_file: str, credential_key: str) -> None:
    monkeypatch.setattr("app.core.config.settings.google_oauth_client_file", oauth_client_file)
    monkeypatch.setattr(
        "app.core.config.settings.google_redirect_uri",
        "http://localhost:18080/auth/google/callback",
    )
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)


@pytest.fixture
def client(db_session, auth_headers, google_settings):
    from tests.conftest import AuthTestClient

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield AuthTestClient(test_client, auth_headers)
    app.dependency_overrides.clear()


def _drive_file(
    file_id: str,
    name: str = "Sample",
    mime_type: str = "text/plain",
    modified_time: str = "2026-08-29T10:00:00.000Z",
    parents: list[str] | None = None,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "createdTime": "2026-08-28T08:00:00.000Z",
        "modifiedTime": modified_time,
        "size": "42",
        "md5Checksum": "abc123",
        "parents": parents or ["parent-1"],
        "driveId": "drive-1",
        "trashed": False,
        "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
    }


class FakeDriveTransport:
    def __init__(
        self,
        start_page_token: str = "bootstrap-start-token",
        file_pages: list[tuple[list[dict], str | None]] | None = None,
        change_pages: list[tuple[list[dict], str | None, str | None]] | None = None,
        file_page_failures: dict[int, BaseException] | None = None,
        change_page_failures: dict[int, BaseException] | None = None,
        fail_list_files_once: bool = False,
    ) -> None:
        self.start_page_token = start_page_token
        self.file_pages = file_pages or []
        self.change_pages = change_pages or []
        self.file_page_failures = file_page_failures or {}
        self.change_page_failures = change_page_failures or {}
        self.fail_list_files_once = fail_list_files_once
        self._list_files_failed = False
        self.file_page_index = 0
        self.change_page_index = 0
        self.calls: list[tuple] = []
        self.closed = False

    def get_start_page_token(self, access_token: str) -> str:
        self.calls.append(("get_start_page_token", access_token))
        return self.start_page_token

    def list_files(
        self,
        access_token: str,
        page_token: str | None,
        page_size: int,
    ) -> DriveFilesPage:
        self.calls.append(("list_files", access_token, page_token, page_size))
        if self.fail_list_files_once and not self._list_files_failed:
            self._list_files_failed = True
            raise GoogleApiError("list failed", operation="list_files")
        page_index = self.file_page_index
        if page_index in self.file_page_failures:
            raise self.file_page_failures[page_index]
        if self.file_page_index >= len(self.file_pages):
            return DriveFilesPage(files=[], next_page_token=None)
        files, next_token = self.file_pages[self.file_page_index]
        self.file_page_index += 1
        return DriveFilesPage(files=list(files), next_page_token=next_token)

    def list_changes(
        self,
        access_token: str,
        page_token: str,
        page_size: int,
    ) -> DriveChangesPage:
        self.calls.append(("list_changes", access_token, page_token, page_size))
        page_index = self.change_page_index
        if page_index in self.change_page_failures:
            raise self.change_page_failures[page_index]
        if self.change_page_index >= len(self.change_pages):
            return DriveChangesPage(changes=[], next_page_token=None, new_start_page_token=None)
        changes, next_token, new_start = self.change_pages[self.change_page_index]
        self.change_page_index += 1
        return DriveChangesPage(
            changes=list(changes),
            next_page_token=next_token,
            new_start_page_token=new_start,
        )

    def close(self) -> None:
        self.closed = True


def _create_account(
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


def _build_sync_service(
    db_session,
    credential_key: str,
    oauth_client_file: str,
    transport: FakeDriveTransport,
    max_items_per_run: int = 500,
) -> DriveSyncService:
    encryption = CredentialEncryption(credential_key)
    account_store = GoogleAccountStore(db_session, encryption)
    oauth_service = GoogleOAuthService(
        oauth_client_file,
        "http://localhost:18080/auth/google/callback",
        http_client=httpx.Client(),
    )
    token_manager = GoogleTokenManager(db_session, account_store, oauth_service)
    job_queue = JobQueueService(db_session)
    return DriveSyncService(
        session=db_session,
        account_store=account_store,
        token_manager=token_manager,
        transport=transport,
        job_queue=job_queue,
        max_items_per_run=max_items_per_run,
    )


def _prefill_drive_object(
    db_session,
    account_id: uuid.UUID,
    file_id: str,
    name: str = "Existing",
    file_item: dict | None = None,
) -> Object:
    source = file_item if file_item is not None else _drive_file(file_id, name=name)
    normalized = normalize_drive_file(source, account_id)
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind=normalized["kind"],
        provider=normalized["provider"],
        external_id=normalized["external_id"],
        origin=normalized["origin"],
        state=normalized["state"],
        title=normalized["title"],
        metadata_=normalized["metadata"],
        canonical_uri=normalized["canonical_uri"],
        occurred_at=normalized.get("occurred_at"),
    )
    db_session.add(obj)
    db_session.commit()
    return obj


def _embed_jobs_for_object(db_session, object_id: uuid.UUID) -> list[Job]:
    return [
        job
        for job in db_session.scalars(select(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)).all()
        if (job.payload or {}).get("object_id") == str(object_id)
    ]


def test_oauth_authorization_url_includes_drive_readonly_scope(
    oauth_client_file: str,
) -> None:
    service = GoogleOAuthService(
        oauth_client_file,
        "http://localhost:18080/auth/google/callback",
    )
    url = service.build_authorization_url("state-token")
    params = parse_qs(urlparse(url).query)
    scope = params["scope"][0]
    assert DRIVE_READONLY_SCOPE in scope.split()
    assert GMAIL_READONLY_SCOPE in scope.split()
    assert CALENDAR_READONLY_SCOPE in scope.split()
    assert DRIVE_READONLY_SCOPE in GOOGLE_OAUTH_SCOPES


def test_old_account_without_drive_scope_reports_drive_unavailable(
    db_session,
    credential_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)
    _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE],
    )
    snapshot = ConnectionStatusService(db_session, BOOTSTRAP_USER_ID).snapshot()
    assert snapshot.google.gmail_available is True
    assert snapshot.google.calendar_available is True
    assert snapshot.google.drive_available is False


def test_old_account_drive_sync_fails_before_drive_api(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE],
    )
    transport = FakeDriveTransport()
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    with pytest.raises(GoogleConnectorError, match="google drive scope not granted"):
        service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert transport.calls == []


def test_reauthorized_account_with_drive_scope_reports_drive_available(
    db_session,
    credential_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)
    _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    snapshot = ConnectionStatusService(db_session, BOOTSTRAP_USER_ID).snapshot()
    assert snapshot.google.drive_available is True


def test_bootstrap_records_start_token_processes_files_and_completes(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(
        start_page_token="start-boundary",
        file_pages=[
            ([_drive_file("file-1"), _drive_file("file-2")], "page-token-2"),
            ([_drive_file("file-3")], None),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 3
    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["bootstrap_complete"] is True
    assert state["changes_page_token"] == "start-boundary"
    assert state["bootstrap_page_token"] is None
    assert state["bootstrap_start_page_token"] is None
    assert transport.calls[0][0] == "get_start_page_token"
    assert any(call[0] == "list_files" for call in transport.calls)


def test_global_hard_cap_limits_items_per_run(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(
        file_pages=[
            (
                [
                    _drive_file("file-1"),
                    _drive_file("file-2"),
                    _drive_file("file-3"),
                ],
                "page-2",
            ),
        ],
    )
    service = _build_sync_service(
        db_session,
        credential_key,
        oauth_client_file,
        transport,
        max_items_per_run=2,
    )
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 2
    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["bootstrap_complete"] is False
    assert state["bootstrap_page_token"] is None


def test_bootstrap_interruption_does_not_skip_unprocessed_items(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(
        file_pages=[
            (
                [
                    _drive_file("file-1"),
                    _drive_file("file-2"),
                    _drive_file("file-3"),
                ],
                "page-2",
            ),
        ],
    )
    service = _build_sync_service(
        db_session,
        credential_key,
        oauth_client_file,
        transport,
        max_items_per_run=2,
    )
    first = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert first["created"] == 2
    db_session.refresh(account)
    interrupted_state = normalize_drive_sync_state(account.drive_sync_state)
    assert interrupted_state["bootstrap_page_token"] is None
    list_files_calls = [call for call in transport.calls if call[0] == "list_files"]
    assert len(list_files_calls) == 1


def test_unchanged_bootstrap_consumes_budget(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    for file_id in ("unch-1", "unch-2", "unch-3", "unch-4"):
        _prefill_drive_object(db_session, account.id, file_id, file_item=_drive_file(file_id))

    unchanged_files = [
        _drive_file("unch-1"),
        _drive_file("unch-2"),
        _drive_file("unch-3"),
        _drive_file("unch-4"),
    ]
    transport = FakeDriveTransport(
        file_pages=[
            (
                unchanged_files,
                "page-2",
            ),
        ],
    )
    service = _build_sync_service(
        db_session,
        credential_key,
        oauth_client_file,
        transport,
        max_items_per_run=2,
    )
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["synchronized"] == 2
    assert result["unchanged"] == 2
    list_files_calls = [call for call in transport.calls if call[0] == "list_files"]
    assert len(list_files_calls) == 1
    assert list_files_calls[0][3] == 2


def test_unchanged_incremental_consumes_budget(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    for file_id in ("inc-1", "inc-2", "inc-3"):
        _prefill_drive_object(db_session, account.id, file_id, file_item=_drive_file(file_id))

    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
            "changes_page_token": "changes-token-1",
        },
    )
    db_session.commit()

    def _unchanged_change(file_id: str) -> dict:
        return {
            "fileId": file_id,
            "removed": False,
            "file": _drive_file(file_id),
        }

    transport = FakeDriveTransport(
        change_pages=[
            (
                [_unchanged_change("inc-1"), _unchanged_change("inc-2"), _unchanged_change("inc-3")],
                "changes-token-2",
                None,
            ),
        ],
    )
    service = _build_sync_service(
        db_session,
        credential_key,
        oauth_client_file,
        transport,
        max_items_per_run=2,
    )
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["synchronized"] == 2
    assert result["unchanged"] == 2
    list_changes_calls = [call for call in transport.calls if call[0] == "list_changes"]
    assert len(list_changes_calls) == 1
    assert list_changes_calls[0][3] == 2


def test_removed_unknown_item_consumes_budget(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "changes_page_token": "changes-token-1",
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
        },
    )
    db_session.commit()

    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {"fileId": "missing-1", "removed": True},
                    {"fileId": "missing-2", "removed": True},
                    {"fileId": "missing-3", "removed": True},
                ],
                "changes-token-2",
                None,
            ),
        ],
    )
    service = _build_sync_service(
        db_session,
        credential_key,
        oauth_client_file,
        transport,
        max_items_per_run=2,
    )
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["synchronized"] == 2
    assert result["unchanged"] == 2
    list_changes_calls = [call for call in transport.calls if call[0] == "list_changes"]
    assert len(list_changes_calls) == 1


def test_bootstrap_start_token_survives_list_files_failure(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(
        start_page_token="T1",
        file_pages=[([_drive_file("survive-1")], None)],
        fail_list_files_once=True,
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    with pytest.raises(GoogleApiError):
        service.sync_account(account.id, BOOTSTRAP_USER_ID)

    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["bootstrap_start_page_token"] == "T1"
    assert state["bootstrap_page_token"] is None

    transport.file_page_index = 0
    transport._list_files_failed = False
    transport.fail_list_files_once = False
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 1
    start_token_calls = [call for call in transport.calls if call[0] == "get_start_page_token"]
    assert len(start_token_calls) == 1


def test_bootstrap_page_cursor_survives_later_failure(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(
        file_pages=[
            ([_drive_file("page-1a"), _drive_file("page-1b")], "P2"),
            ([_drive_file("page-2a")], None),
        ],
        file_page_failures={1: GoogleApiError("page 2 failed", operation="list_files")},
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    with pytest.raises(GoogleApiError):
        service.sync_account(account.id, BOOTSTRAP_USER_ID)

    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["bootstrap_page_token"] == "P2"

    transport.file_page_index = 1
    transport.file_page_failures = {}
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 1
    list_files_calls = [call for call in transport.calls if call[0] == "list_files"]
    assert any(call[2] == "P2" for call in list_files_calls)


def test_incremental_page_cursor_survives_later_failure(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
            "changes_page_token": "C1",
        },
    )
    db_session.commit()

    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {
                        "fileId": "chg-1",
                        "removed": False,
                        "file": _drive_file("chg-1"),
                    },
                ],
                "C2",
                None,
            ),
            (
                [
                    {
                        "fileId": "chg-2",
                        "removed": False,
                        "file": _drive_file("chg-2"),
                    },
                ],
                None,
                "new-start",
            ),
        ],
        change_page_failures={1: GoogleApiError("changes page 2 failed", operation="list_changes")},
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    with pytest.raises(GoogleApiError):
        service.sync_account(account.id, BOOTSTRAP_USER_ID)

    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["changes_page_token"] == "C2"

    transport.change_page_index = 1
    transport.change_page_failures = {}
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 1
    list_changes_calls = [call for call in transport.calls if call[0] == "list_changes"]
    assert any(call[2] == "C2" for call in list_changes_calls)


def test_incremental_changes_update_cursor_after_full_page(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
            "changes_page_token": "changes-token-1",
        },
    )
    db_session.commit()

    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {
                        "fileId": "file-4",
                        "removed": False,
                        "file": _drive_file("file-4", name="Updated doc"),
                    },
                ],
                "changes-token-2",
                None,
            ),
            (
                [
                    {
                        "fileId": "file-5",
                        "removed": False,
                        "file": _drive_file("file-5"),
                    },
                ],
                None,
                "new-start-token",
            ),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 2
    db_session.refresh(account)
    state = normalize_drive_sync_state(account.drive_sync_state)
    assert state["changes_page_token"] == "new-start-token"


def test_identical_duplicate_does_not_enqueue_embed(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    file_item = _drive_file("dup-file", name="Same title")
    change_record = {
        "fileId": "dup-file",
        "removed": False,
        "file": file_item,
    }
    transport = FakeDriveTransport(
        file_pages=[([file_item], None)],
        change_pages=[
            ([change_record], None, "new-start"),
            ([change_record], None, "new-start-2"),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    first = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert first["created"] == 1
    obj = db_session.scalar(
        select(Object).where(
            Object.provider == GOOGLE_DRIVE_PROVIDER,
            Object.external_id == "dup-file",
        )
    )
    assert obj is not None
    assert len(_embed_jobs_for_object(db_session, obj.id)) == 1

    second = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert second["unchanged"] == 1
    assert len(_embed_jobs_for_object(db_session, obj.id)) == 1


def test_title_change_enqueues_single_embed_job(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "changes_page_token": "token-1",
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
        },
    )
    db_session.commit()

    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider=GOOGLE_DRIVE_PROVIDER,
        external_id="title-file",
        origin="source",
        state="observed",
        title="Old title",
        metadata_={"account_id": str(account.id), "file_id": "title-file"},
        canonical_uri=build_canonical_uri("title-file"),
    )
    db_session.add(obj)
    db_session.commit()

    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {
                        "fileId": "title-file",
                        "removed": False,
                        "file": _drive_file("title-file", name="New title"),
                    },
                ],
                None,
                "new-start",
            ),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["updated"] == 1
    db_session.refresh(obj)
    assert obj.title == "New title"
    assert len(_embed_jobs_for_object(db_session, obj.id)) == 1


def test_metadata_only_change_does_not_enqueue_embed(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "changes_page_token": "token-1",
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
        },
    )
    db_session.commit()

    normalized = normalize_drive_file(_drive_file("meta-file", name="Stable title"), account.id)
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind=normalized["kind"],
        provider=normalized["provider"],
        external_id=normalized["external_id"],
        origin=normalized["origin"],
        state=normalized["state"],
        title=normalized["title"],
        metadata_=normalized["metadata"],
        canonical_uri=normalized["canonical_uri"],
        occurred_at=normalized.get("occurred_at"),
    )
    db_session.add(obj)
    db_session.commit()

    updated_file = _drive_file(
        "meta-file",
        name="Stable title",
        modified_time="2026-08-30T12:00:00.000Z",
        parents=["parent-1", "parent-2"],
    )
    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {
                        "fileId": "meta-file",
                        "removed": False,
                        "file": updated_file,
                    },
                ],
                None,
                "new-start",
            ),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["updated"] == 1
    assert len(_embed_jobs_for_object(db_session, obj.id)) == 0


def test_removed_item_soft_deletes_without_physical_delete(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider=GOOGLE_DRIVE_PROVIDER,
        external_id="gone-file",
        origin="source",
        state="observed",
        title="Gone",
        metadata_={"account_id": str(account.id), "file_id": "gone-file"},
        canonical_uri=build_canonical_uri("gone-file"),
    )
    db_session.add(obj)
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "changes_page_token": "token-1",
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
        },
    )
    db_session.commit()
    object_id = obj.id

    transport = FakeDriveTransport(
        change_pages=[
            (
                [{"fileId": "gone-file", "removed": True}],
                None,
                "new-start",
            ),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["tombstoned"] == 1
    persisted = db_session.get(Object, object_id)
    assert persisted is not None
    assert persisted.status == "deleted"


def test_restored_item_clears_deleted_status(
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    obj = Object(
        user_id=BOOTSTRAP_USER_ID,
        kind="file",
        provider=GOOGLE_DRIVE_PROVIDER,
        external_id="restore-file",
        origin="source",
        state="observed",
        title="Restored",
        status="deleted",
        metadata_={"account_id": str(account.id), "file_id": "restore-file"},
        canonical_uri=build_canonical_uri("restore-file"),
    )
    db_session.add(obj)
    store = GoogleAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    store.update_drive_sync_state(
        account,
        {
            "bootstrap_complete": True,
            "changes_page_token": "token-1",
            "bootstrap_start_page_token": None,
            "bootstrap_page_token": None,
        },
    )
    db_session.commit()
    object_id = obj.id

    transport = FakeDriveTransport(
        change_pages=[
            (
                [
                    {
                        "fileId": "restore-file",
                        "removed": False,
                        "file": _drive_file("restore-file", name="Restored"),
                    },
                ],
                None,
                "new-start",
            ),
        ],
    )
    service = _build_sync_service(db_session, credential_key, oauth_client_file, transport)
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    persisted = db_session.get(Object, object_id)
    assert persisted is not None
    assert persisted.status is None


def test_folder_kind_and_file_kind_normalization() -> None:
    folder = normalize_drive_file(
        _drive_file("folder-1", name="Folder", mime_type=GOOGLE_DRIVE_FOLDER_MIME),
        uuid.uuid4(),
    )
    assert folder is not None
    assert folder["kind"] == "folder"
    file_norm = normalize_drive_file(_drive_file("file-1"), uuid.uuid4())
    assert file_norm is not None
    assert file_norm["kind"] == "file"


def test_cross_user_account_id_rejected(client, db_session, credential_key: str) -> None:
    other_user = uuid.uuid4()
    db_session.add(User(id=other_user, display_name="Other"))
    db_session.flush()
    other_account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
        user_id=other_user,
        email="other@example.com",
    )
    response = client.post(
        f"/connectors/google/drive/sync?account_id={other_account.id}",
    )
    assert response.status_code == 404


def test_tokens_absent_from_metadata_endpoint_and_errors(
    client,
    db_session,
    credential_key: str,
    oauth_client_file: str,
) -> None:
    account = _create_account(
        db_session,
        credential_key,
        scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE, DRIVE_READONLY_SCOPE],
    )
    transport = FakeDriveTransport(file_pages=[([_drive_file("safe-file")], None)])

    def _fake_build(session, credential_key, client_file, redirect_uri, max_items_per_run=500, http_client=None):
        return _build_sync_service(
            session,
            credential_key,
            client_file,
            transport,
            max_items_per_run=max_items_per_run,
        )

    import app.api.google as google_api

    original = google_api.build_drive_sync_service
    google_api.build_drive_sync_service = _fake_build
    try:
        response = client.post(f"/connectors/google/drive/sync?account_id={account.id}")
        assert response.status_code == 200
        assert ACCESS_TOKEN not in response.text
        assert REFRESH_TOKEN not in response.text
        obj = db_session.scalar(
            select(Object).where(Object.external_id == "safe-file")
        )
        assert obj is not None
        assert ACCESS_TOKEN not in str(obj.metadata_)
        assert REFRESH_TOKEN not in str(obj.metadata_)

        no_scope = _create_account(
            db_session,
            credential_key,
            scopes=[GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE],
            email="legacy@example.com",
        )
        denied = client.post(f"/connectors/google/drive/sync?account_id={no_scope.id}")
        assert denied.status_code == 400
        assert ACCESS_TOKEN not in denied.text
        assert REFRESH_TOKEN not in denied.text
    finally:
        google_api.build_drive_sync_service = original


def test_owned_transport_closed_injected_client_not_closed(
    oauth_client_file: str,
) -> None:
    owned = DriveTransport()
    owned.close()
    assert owned._http.is_closed

    shared_client = httpx.Client()
    injected = DriveTransport(http_client=shared_client)
    injected.close()
    assert not shared_client.is_closed
    shared_client.close()


def test_drive_transport_calls_fixed_google_api_base() -> None:
    calls: list[str] = []

    class RecordingClient:
        def get(self, url: str, params=None, headers=None, **kwargs):
            calls.append(url)
            if url.endswith("/changes/startPageToken"):
                return httpx.Response(200, json={"startPageToken": "t1"})
            if url.endswith("/files"):
                return httpx.Response(200, json={"files": [], "nextPageToken": None})
            if url.endswith("/changes"):
                return httpx.Response(
                    200,
                    json={"changes": [], "nextPageToken": None, "newStartPageToken": "t2"},
                )
            raise AssertionError(url)

    transport = DriveTransport(http_client=RecordingClient())
    transport.get_start_page_token(ACCESS_TOKEN)
    transport.list_files(ACCESS_TOKEN, None, 10)
    transport.list_changes(ACCESS_TOKEN, "t1", 10)
    transport.close()
    assert all(url.startswith(DRIVE_API_BASE) for url in calls)
