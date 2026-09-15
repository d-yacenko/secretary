from datetime import UTC, datetime, timedelta
import asyncio

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.api.teams_webhook import teams_graph_webhook
from app.connectors.teams.notifications import (
    enqueue_graph_notifications,
    parse_chat_message_resource,
    process_graph_notification,
)
from app.connectors.teams.subscriptions import TeamsSubscriptionService
from app.connectors.teams.sync import TeamsSyncService
from app.connectors.teams.transport import FakeTeamsTransport, TeamsHttpTransport
from app.db.models import Job, Object, TeamsSubscription
from app.jobs.constants import JOB_TYPE_PROCESS_TEAMS_NOTIFICATION, JOB_TYPE_SYNC_TEAMS
from app.services.job_queue_service import JobQueueService
from tests.test_teams_a import (
    CHAT_GROUP,
    CHAT_ONE,
    TEAMS_USER_ID,
    TENANT_ID,
    _connect_account,
    _store,
    _user,
)


@pytest.fixture
def credential_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def teams_settings(monkeypatch: pytest.MonkeyPatch, credential_key: str) -> str:
    monkeypatch.setattr("app.core.config.settings.secretary_credential_key", credential_key)
    monkeypatch.setattr("app.core.config.settings.microsoft_oauth_client_id", "client-id")
    monkeypatch.setattr("app.core.config.settings.microsoft_oauth_client_secret", "client-secret")
    monkeypatch.setattr(
        "app.core.config.settings.microsoft_redirect_uri",
        "http://localhost:18080/auth/teams/callback",
    )
    return credential_key


def _message(message_id: str, chat_id: str, sender_id: str) -> dict:
    return {
        "id": message_id,
        "chatId": chat_id,
        "messageType": "message",
        "createdDateTime": "2026-09-15T12:00:00Z",
        "from": {"user": {"id": sender_id, "displayName": "Sender"}},
        "body": {"contentType": "text", "content": "hello"},
    }


def test_notification_resource_parser_rejects_channels() -> None:
    assert parse_chat_message_resource(
        f"/users/{TEAMS_USER_ID}/chats('chat')/messages('message')"
    ) == (TEAMS_USER_ID, "chat", "message")
    assert parse_chat_message_resource("/teams/t/channels/c/messages/m") is None


def test_graph_webhook_validation_is_plain_text_without_database() -> None:
    class _Request:
        method = "POST"

        async def json(self) -> dict:
            raise AssertionError("validation must not parse a body")

    response = asyncio.run(teams_graph_webhook(_Request(), validation_token="opaque token"))
    assert response.status_code == 200
    assert response.media_type == "text/plain"
    assert response.body == b"opaque token"
    get_request = _Request()
    get_request.method = "GET"
    get_response = asyncio.run(teams_graph_webhook(get_request, validation_token="get-token"))
    assert get_response.body == b"get-token"


def test_graph_transport_uses_v1_subscription_endpoint_and_basic_payload() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "subscription-1",
                    "resource": "/users/user-1/chats/getAllMessages",
                    "expirationDateTime": "2026-09-15T15:00:00Z",
                },
            )
        return httpx.Response(200, json={"expirationDateTime": "2026-09-15T15:00:00Z"})

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    transport = TeamsHttpTransport("tok", http_client=client)
    payload = {
        "changeType": "created,updated",
        "notificationUrl": "https://example.test/webhooks/teams",
        "resource": "/users/user-1/chats/getAllMessages",
        "includeResourceData": False,
        "expirationDateTime": "2026-09-15T15:00:00Z",
        "clientState": "random",
    }
    transport.create_subscription(payload)
    transport.renew_subscription("subscription-1", {"expirationDateTime": payload["expirationDateTime"]})
    transport.delete_subscription("subscription-1")
    assert [request.method for request in calls] == ["POST", "PATCH", "DELETE"]
    assert all("/v1.0/" in str(request.url) and "beta" not in str(request.url) for request in calls)
    assert httpx.Request("POST", "https://example.test", json=payload).content == calls[0].content


def test_subscription_lifecycle_persists_encrypted_state_and_renews(
    db_session, teams_settings
) -> None:
    user = _user(db_session)
    account = _connect_account(db_session, teams_settings, user.id)
    store = _store(db_session, teams_settings)
    service = TeamsSubscriptionService(db_session, store)
    fake = FakeTeamsTransport()
    now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    created = service.ensure(
        account,
        fake,
        notification_url="https://example.test/webhooks/teams",
        now=now,
    )
    assert created is not None
    assert created.client_state_encrypted != ""
    assert created.client_state_encrypted != fake.subscription_response.get("clientState")
    assert fake.subscription_create_calls[0]["includeResourceData"] is False
    assert fake.subscription_create_calls[0]["lifecycleNotificationUrl"] == (
        "https://example.test/webhooks/teams"
    )
    assert fake.subscription_create_calls[0]["resource"] == (
        f"/users/{TEAMS_USER_ID}/chats/getAllMessages"
    )
    created.expires_at = now + timedelta(minutes=1)
    renewed = service.ensure(
        account,
        fake,
        notification_url="https://example.test/webhooks/teams",
        now=now,
    )
    assert renewed is created
    assert len(fake.subscription_renew_calls) == 1
    assert fake.subscription_renew_calls[0][0] == "subscription-1"


def test_reconciliation_reuses_cached_chat_metadata_but_keeps_message_read(
    db_session, teams_settings
) -> None:
    user = _user(db_session)
    account = _connect_account(
        db_session,
        teams_settings,
        user.id,
        sync_start=datetime(2026, 9, 15, 11, 0, tzinfo=UTC),
    )
    fake = FakeTeamsTransport()
    fake.chats = [
        {
            "id": CHAT_ONE,
            "chatType": "oneOnOne",
            "lastUpdatedDateTime": "2026-09-15T12:00:00Z",
        }
    ]
    fake.messages_by_chat[CHAT_ONE] = [_message("in-one", CHAT_ONE, "other")]
    service = TeamsSyncService(
        db_session,
        _store(db_session, teams_settings),
        JobQueueService(db_session),
        transport=fake,
    )
    service.sync_account(account.id, user.id)
    assert fake.list_chats_calls == 1
    assert fake.get_chat_calls == [CHAT_ONE]
    assert fake.list_messages_calls == [CHAT_ONE]
    fake.get_chat_calls.clear()
    fake.list_messages_calls.clear()
    service.sync_account(account.id, user.id)
    assert fake.get_chat_calls == []
    assert fake.list_messages_calls == []


def test_valid_client_state_enqueues_once_and_invalid_or_unknown_is_ignored(
    db_session, teams_settings
) -> None:
    user = _user(db_session)
    account = _connect_account(db_session, teams_settings, user.id)
    store = _store(db_session, teams_settings)
    row = TeamsSubscription(
        account_id=account.id,
        user_id=user.id,
        subscription_id="sub-1",
        resource=f"/users/{TEAMS_USER_ID}/chats/getAllMessages",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        client_state_encrypted=store.encrypt_secret("state"),
    )
    db_session.add(row)
    db_session.flush()
    notification = {
        "subscriptionId": "sub-1",
        "clientState": "state",
        "tenantId": TENANT_ID,
        "resource": f"/users/{TEAMS_USER_ID}/chats('{CHAT_ONE}')/messages('m-1')",
    }
    assert enqueue_graph_notifications(db_session, {"value": [notification]}) == 1
    assert enqueue_graph_notifications(db_session, {"value": [notification]}) == 1
    jobs = list(
        db_session.scalars(
            select(Job).where(Job.type == JOB_TYPE_PROCESS_TEAMS_NOTIFICATION)
        )
    )
    assert len(jobs) == 1
    bad_state = dict(notification, clientState="wrong")
    unknown = dict(notification, subscriptionId="unknown")
    assert enqueue_graph_notifications(db_session, {"value": [bad_state, unknown]}) == 0


def test_targeted_notification_materializes_supported_chats_and_filters_own_message(
    db_session, teams_settings
) -> None:
    user = _user(db_session)
    account = _connect_account(db_session, teams_settings, user.id)
    store = _store(db_session, teams_settings)
    db_session.add(
        TeamsSubscription(
            account_id=account.id,
            user_id=user.id,
            subscription_id="sub-targeted",
            resource=f"/users/{TEAMS_USER_ID}/chats/getAllMessages",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_state_encrypted=store.encrypt_secret("state"),
        )
    )
    fake = FakeTeamsTransport()
    fake.me = {"id": TEAMS_USER_ID}
    fake.chats = [
        {"id": CHAT_ONE, "chatType": "oneOnOne", "members": []},
        {"id": CHAT_GROUP, "chatType": "group", "members": []},
    ]
    fake.messages_by_chat[CHAT_ONE] = [_message("in-one", CHAT_ONE, "other")]
    fake.messages_by_chat[CHAT_GROUP] = [_message("in-group", CHAT_GROUP, "other")]
    process_graph_notification(
        db_session,
        {"account_id": str(account.id), "subscription_id": "sub-targeted", "chat_id": CHAT_ONE, "message_id": "in-one"},
        user.id,
        transport=fake,
    )
    process_graph_notification(
        db_session,
        {"account_id": str(account.id), "subscription_id": "sub-targeted", "chat_id": CHAT_GROUP, "message_id": "in-group"},
        user.id,
        transport=fake,
    )
    fake.messages_by_chat[CHAT_ONE] = [_message("out-own", CHAT_ONE, TEAMS_USER_ID)]
    process_graph_notification(
        db_session,
        {"account_id": str(account.id), "subscription_id": "sub-targeted", "chat_id": CHAT_ONE, "message_id": "out-own"},
        user.id,
        transport=fake,
    )
    objects = list(db_session.scalars(select(Object).where(Object.user_id == user.id)))
    assert {obj.external_id.split("|")[-1] for obj in objects} == {"in-one", "in-group", "out-own"}
    assert fake.get_chat_message_calls == [
        (CHAT_ONE, "in-one"),
        (CHAT_GROUP, "in-group"),
        (CHAT_ONE, "out-own"),
    ]


def test_lifecycle_missed_triggers_reconciliation(db_session, teams_settings) -> None:
    user = _user(db_session)
    account = _connect_account(db_session, teams_settings, user.id)
    store = _store(db_session, teams_settings)
    JobQueueService(db_session).ensure_recurring_source_job(
        JOB_TYPE_SYNC_TEAMS, account.id, user.id
    )
    db_session.add(
        TeamsSubscription(
            account_id=account.id,
            user_id=user.id,
            subscription_id="sub-life",
            resource=f"/users/{TEAMS_USER_ID}/chats/getAllMessages",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            client_state_encrypted=store.encrypt_secret("state"),
        )
    )
    db_session.flush()
    queued = enqueue_graph_notifications(
        db_session,
        {
            "value": [
                {
                    "subscriptionId": "sub-life",
                    "clientState": "state",
                    "tenantId": TENANT_ID,
                    "lifecycleEvent": "missed",
                }
            ]
        },
    )
    assert queued == 1
    job = db_session.scalar(select(Job).where(Job.type == JOB_TYPE_SYNC_TEAMS))
    assert job is not None
    assert job.run_after <= datetime.now(UTC)
