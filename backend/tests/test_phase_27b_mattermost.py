import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.connectors.mattermost.credentials import MattermostAccountStore
from app.connectors.mattermost.errors import MattermostSecurityError
from app.connectors.mattermost.normalize import (
    build_external_id,
    normalize_mattermost_post,
    normalize_server_url,
    validate_server_url_allowlist,
)
from app.connectors.mattermost.sync import build_mattermost_sync_service
from app.connectors.mattermost.transport import FakeMattermostTransport
from app.db.models import Job, MattermostAccount, Object, User
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.main import app
from app.users.bootstrap import BOOTSTRAP_USER_ID

ALLOWED_URL = "https://mm.example.com"
PAT = "mattermost-personal-access-token"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _post(
    post_id: str,
    channel_id: str,
    message: str,
    create_at: datetime,
    user_id: str = "author-1",
    update_at: datetime | None = None,
    post_type: str = "",
    file_ids: list[str] | None = None,
) -> dict:
    update = update_at or create_at
    payload = {
        "id": post_id,
        "channel_id": channel_id,
        "user_id": user_id,
        "message": message,
        "create_at": _ms(create_at),
        "update_at": _ms(update),
        "type": post_type,
        "root_id": "",
        "file_ids": file_ids or [],
    }
    return payload


def _channel(
    channel_id: str,
    name: str,
    display_name: str,
    channel_type: str,
    last_post_at: datetime,
    team_id: str | None = "team-1",
) -> dict:
    return {
        "id": channel_id,
        "name": name,
        "display_name": display_name,
        "type": channel_type,
        "team_id": team_id,
        "last_post_at": _ms(last_post_at),
    }


@pytest.fixture
def credential_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def mattermost_settings(monkeypatch: pytest.MonkeyPatch, credential_key: str) -> None:
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)
    monkeypatch.setattr(
        "app.core.config.settings.mattermost_allowed_base_urls",
        ALLOWED_URL,
    )


@pytest.fixture
def client(db_session, auth_headers, mattermost_settings):
    from tests.conftest import AuthTestClient

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield AuthTestClient(test_client, auth_headers)
    app.dependency_overrides.clear()


def _connect_account(
    db_session,
    credential_key: str,
    user_id: uuid.UUID = BOOTSTRAP_USER_ID,
) -> MattermostAccount:
    store = MattermostAccountStore(
        db_session,
        MattermostAccountStore.build_encryption(credential_key),
    )
    account = store.upsert_account(
        user_id=user_id,
        normalized_server_url=ALLOWED_URL,
        remote_user_id="user-1",
        username="alice",
        access_token=PAT,
        display_name="Alice",
        email="alice@example.com",
    )
    db_session.commit()
    return account


def _build_sync_service(
    db_session,
    credential_key: str,
    transport: FakeMattermostTransport,
    now: datetime,
):
    def transport_factory(snapshot):
        return transport

    return build_mattermost_sync_service(
        session=db_session,
        credential_key=credential_key,
        sync_days=14,
        max_channels=50,
        initial_posts_per_channel=100,
        max_posts_per_run=500,
        overlap_seconds=300,
        transport_factory=transport_factory,
        now_factory=lambda: now,
    )


def test_normalize_server_url_rejects_userinfo_query_fragment_and_http() -> None:
    with pytest.raises(MattermostSecurityError, match="userinfo"):
        normalize_server_url("https://user:pass@mm.example.com")
    with pytest.raises(MattermostSecurityError, match="query"):
        normalize_server_url("https://mm.example.com?x=1")
    with pytest.raises(MattermostSecurityError, match="fragment"):
        normalize_server_url("https://mm.example.com#frag")
    with pytest.raises(MattermostSecurityError, match="https"):
        normalize_server_url("http://mm.example.com")


def test_empty_allowlist_disables_mattermost() -> None:
    with pytest.raises(MattermostSecurityError, match="not configured"):
        validate_server_url_allowlist(ALLOWED_URL, frozenset())


def test_mattermost_connect_verifies_pat_and_upserts_account(
    client,
    db_session,
    credential_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMattermostTransport()

    def _fake_transport(**kwargs):
        return fake

    monkeypatch.setattr("app.api.mattermost.MattermostHttpTransport", _fake_transport)

    response = client.post(
        "/connectors/mattermost/connect",
        json={"server_url": ALLOWED_URL, "access_token": PAT},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "connected"
    assert payload["username"] == "alice"
    assert PAT not in response.text

    account = db_session.scalar(
        select(MattermostAccount).where(MattermostAccount.username == "alice")
    )
    assert account is not None
    assert account.access_token_encrypted != PAT
    store = MattermostAccountStore(
        db_session,
        MattermostAccountStore.build_encryption(credential_key),
    )
    assert store.get_access_token(account) == PAT


def test_mattermost_connect_rejects_unauthorized(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMattermostTransport(unauthorized_on_me=True)

    monkeypatch.setattr(
        "app.api.mattermost.MattermostHttpTransport",
        lambda **kwargs: fake,
    )
    response = client.post(
        "/connectors/mattermost/connect",
        json={"server_url": ALLOWED_URL, "access_token": "bad-token"},
    )
    assert response.status_code == 401
    assert PAT not in response.text


def test_mattermost_connect_rejects_redirect(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeMattermostTransport(redirect_on_me=True)
    monkeypatch.setattr(
        "app.api.mattermost.MattermostHttpTransport",
        lambda **kwargs: fake,
    )
    response = client.post(
        "/connectors/mattermost/connect",
        json={"server_url": ALLOWED_URL, "access_token": PAT},
    )
    assert response.status_code == 400
    assert "redirect" in response.json()["detail"].lower()


def test_mattermost_connect_rejects_non_allowlisted_server(client) -> None:
    response = client.post(
        "/connectors/mattermost/connect",
        json={"server_url": "https://other.example.com", "access_token": PAT},
    )
    assert response.status_code == 400


def test_channel_discovery_covers_public_private_dm_gm(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    channels = [
        _channel("ch-open", "town-square", "Town Square", "O", now),
        _channel("ch-private", "private", "Private", "P", now - timedelta(minutes=1)),
        _channel("ch-dm", "dm-user", "DM", "D", now - timedelta(minutes=2), team_id=""),
        _channel("ch-gm", "group", "Group", "G", now - timedelta(minutes=3), team_id=""),
    ]
    transport = FakeMattermostTransport(
        channels=channels,
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {
                "id": "author-1",
                "username": "bob",
                "display_name": "Bob",
            }
        },
        posts_by_channel={
            "ch-open": [
                _post("p1", "ch-open", "hello open", now - timedelta(hours=1)),
            ],
            "ch-private": [
                _post("p2", "ch-private", "hello private", now - timedelta(hours=1)),
            ],
            "ch-dm": [
                _post("p3", "ch-dm", "hello dm", now - timedelta(hours=1)),
            ],
            "ch-gm": [
                _post("p4", "ch-gm", "hello gm", now - timedelta(hours=1)),
            ],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 4
    kinds = {
        row.metadata_["channel_type"]
        for row in db_session.scalars(
            select(Object).where(Object.provider == "mattermost")
        ).all()
    }
    assert kinds == {"O", "P", "D", "G"}


def test_channel_discovery_fallback_via_teams(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    transport = FakeMattermostTransport(
        channels=[],
        my_channels_not_found=True,
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        team_channels={
            ("team-1", "user-1"): [
                _channel("ch-fallback", "fallback", "Fallback", "O", now),
            ]
        },
        users_by_id={
            "author-1": {
                "id": "author-1",
                "username": "bob",
                "display_name": "Bob",
            }
        },
        posts_by_channel={
            "ch-fallback": [
                _post("p-fb", "ch-fallback", "fallback msg", now - timedelta(hours=1)),
            ]
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 1


def test_batch_author_resolution_uses_single_users_ids_call(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
            "author-2": {"id": "author-2", "username": "carol", "display_name": "Carol"},
        },
        posts_by_channel={
            "ch-1": [
                _post("p1", "ch-1", "one", now - timedelta(hours=2), user_id="author-1"),
                _post("p2", "ch-1", "two", now - timedelta(hours=1), user_id="author-2"),
            ],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    user_calls = [call for call in transport.calls if call[0] == "POST"]
    assert user_calls
    assert any(len((call[2] or {}).get("ids", [])) == 2 for call in user_calls)
    assert all(len((call[2] or {}).get("ids", [])) != 1 for call in user_calls)


def test_initial_bounded_sync_and_server_namespaced_idempotency(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    old_post_time = now - timedelta(days=30)
    recent_time = now - timedelta(hours=1)
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={
            "ch-1": [
                _post("old", "ch-1", "too old", old_post_time),
                _post("new", "ch-1", "recent", recent_time),
            ],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(
        db_session,
        credential_key,
        transport,
        now,
    )
    first = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert first["created"] == 1
    obj = db_session.scalar(
        select(Object).where(
            Object.provider == "mattermost",
            Object.external_id == build_external_id(ALLOWED_URL, "new"),
        )
    )
    assert obj is not None

    second = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert second["created"] == 0
    assert second["unchanged"] >= 1


def test_new_post_resumable_catch_up_and_global_cap_without_cursor_skip(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    posts = [
        _post(f"p{i}", "ch-1", f"msg {i}", now - timedelta(minutes=10 - i))
        for i in range(1, 6)
    ]
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={"ch-1": posts},
    )
    account = _connect_account(db_session, credential_key)
    service = build_mattermost_sync_service(
        session=db_session,
        credential_key=credential_key,
        sync_days=14,
        max_channels=50,
        initial_posts_per_channel=100,
        max_posts_per_run=2,
        overlap_seconds=300,
        transport_factory=lambda snapshot: transport,
        now_factory=lambda: now,
    )
    first = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert first["created"] == 2

    account = db_session.scalar(select(MattermostAccount).where(MattermostAccount.id == account.id))
    channel_state = account.sync_state["channels"]["ch-1"]
    assert channel_state["last_processed_post_id"] == "p2"

    transport.posts_by_channel["ch-1"] = posts + [
        _post("p6", "ch-1", "msg 6", now - timedelta(minutes=1)),
    ]
    second = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert second["created"] == 2
    account = db_session.scalar(select(MattermostAccount).where(MattermostAccount.id == account.id))
    assert account.sync_state["channels"]["ch-1"]["last_processed_post_id"] == "p4"


def test_per_channel_independent_cursors(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    transport = FakeMattermostTransport(
        channels=[
            _channel("ch-a", "a", "A", "O", now),
            _channel("ch-b", "b", "B", "O", now - timedelta(minutes=1)),
        ],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={
            "ch-a": [_post("a1", "ch-a", "a msg", now - timedelta(hours=1))],
            "ch-b": [_post("b1", "ch-b", "b msg", now - timedelta(hours=1))],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    service.sync_account(account.id, BOOTSTRAP_USER_ID)

    transport.posts_by_channel["ch-a"].append(
        _post("a2", "ch-a", "a msg 2", now - timedelta(minutes=30))
    )
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    account = db_session.scalar(select(MattermostAccount).where(MattermostAccount.id == account.id))
    assert account.sync_state["channels"]["ch-a"]["last_processed_post_id"] == "a2"
    assert account.sync_state["channels"]["ch-b"]["last_processed_post_id"] == "b1"


def test_edited_post_change_sweep_updates_same_object_and_embeds(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    create_time = now - timedelta(hours=2)
    edit_time = now - timedelta(minutes=10)
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={
            "ch-1": [
                _post("p-edit", "ch-1", "original", create_time, update_at=create_time),
            ],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    obj = db_session.scalar(
        select(Object).where(Object.external_id == build_external_id(ALLOWED_URL, "p-edit"))
    )
    assert obj is not None
    first_object_id = obj.id

    transport.posts_by_channel["ch-1"] = [
        _post("p-edit", "ch-1", "edited body", create_time, update_at=edit_time),
    ]
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["updated"] == 1
    obj = db_session.scalar(
        select(Object).where(Object.external_id == build_external_id(ALLOWED_URL, "p-edit"))
    )
    assert obj.id == first_object_id
    assert obj.body == "edited body"
    jobs = [
        job
        for job in db_session.scalars(select(Job).where(Job.type == JOB_TYPE_EMBED_OBJECT)).all()
        if (job.payload or {}).get("object_id") == str(first_object_id)
    ]
    assert len(jobs) == 2


def test_since_saturation_does_not_advance_edit_watermark(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    saturated_posts = [
        _post(
            f"s{i}",
            "ch-1",
            f"sat {i}",
            now - timedelta(hours=1),
            update_at=now - timedelta(minutes=i % 30),
        )
        for i in range(1000)
    ]
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={"ch-1": saturated_posts[:1]},
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    account = db_session.scalar(select(MattermostAccount).where(MattermostAccount.id == account.id))
    watermark_before = account.sync_state["channels"]["ch-1"].get("edit_sweep_watermark_ms")

    transport.posts_by_channel["ch-1"] = saturated_posts
    service.sync_account(account.id, BOOTSTRAP_USER_ID)
    account = db_session.scalar(select(MattermostAccount).where(MattermostAccount.id == account.id))
    channel_state = account.sync_state["channels"]["ch-1"]
    assert channel_state.get("edit_sweep_watermark_ms") == watermark_before


def test_system_posts_ignored_and_attachment_only_without_download(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    now = utcnow()
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={
            "ch-1": [
                _post(
                    "sys",
                    "ch-1",
                    "",
                    now - timedelta(hours=1),
                    post_type="system_join_channel",
                ),
                _post(
                    "file-only",
                    "ch-1",
                    "",
                    now - timedelta(minutes=30),
                    file_ids=["file-1"],
                ),
            ],
        },
    )
    account = _connect_account(db_session, credential_key)
    service = _build_sync_service(db_session, credential_key, transport, now)
    result = service.sync_account(account.id, BOOTSTRAP_USER_ID)
    assert result["created"] == 1
    obj = db_session.scalar(select(Object).where(Object.provider == "mattermost"))
    assert obj is not None
    assert obj.external_id == build_external_id(ALLOWED_URL, "file-only")
    assert obj.metadata_["file_ids"] == ["file-1"]
    download_calls = [call for call in transport.calls if "files" in call[1]]
    assert download_calls == []


def test_user_isolation_for_mattermost_accounts_and_objects(
    db_session,
    credential_key: str,
    mattermost_settings,
) -> None:
    other_user_id = uuid.uuid4()
    db_session.add(User(id=other_user_id, display_name="Other"))
    db_session.commit()

    store = MattermostAccountStore(
        db_session,
        MattermostAccountStore.build_encryption(credential_key),
    )
    account_a = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        normalized_server_url=ALLOWED_URL,
        remote_user_id="user-1",
        username="alice",
        access_token=PAT,
    )
    account_b = store.upsert_account(
        user_id=other_user_id,
        normalized_server_url=ALLOWED_URL,
        remote_user_id="user-2",
        username="bob",
        access_token="other-token",
    )
    db_session.commit()

    assert store.get_by_id_for_user(account_a.id, other_user_id) is None
    assert store.get_by_id_for_user(account_b.id, BOOTSTRAP_USER_ID) is None

    now = utcnow()
    transport = FakeMattermostTransport(
        channels=[_channel("ch-1", "general", "General", "O", now)],
        teams=[{"id": "team-1", "name": "team", "display_name": "Team"}],
        users_by_id={
            "author-1": {"id": "author-1", "username": "bob", "display_name": "Bob"},
        },
        posts_by_channel={
            "ch-1": [_post("iso", "ch-1", "secret", now - timedelta(hours=1))],
        },
    )
    service = _build_sync_service(db_session, credential_key, transport, now)
    service.sync_account(account_a.id, BOOTSTRAP_USER_ID)
    obj = db_session.scalar(select(Object).where(Object.user_id == BOOTSTRAP_USER_ID))
    assert obj is not None
    other_obj = db_session.scalar(
        select(Object).where(
            Object.user_id == other_user_id,
            Object.external_id == obj.external_id,
        )
    )
    assert other_obj is None


def test_normalize_skips_empty_without_files() -> None:
    from app.connectors.mattermost.normalize import MattermostChannelContext, should_skip_post

    assert should_skip_post({"type": "", "message": "", "file_ids": []})
    post = _post("x", "ch", "", utcnow())
    normalized = normalize_mattermost_post(
        post=post,
        normalized_server_url=ALLOWED_URL,
        channel=MattermostChannelContext(
            channel_id="ch",
            channel_name="general",
            channel_display_name="General",
            channel_type="O",
            team_id="team-1",
            team_name="team",
            team_display_name="Team",
        ),
        author=None,
    )
    assert normalized is None
