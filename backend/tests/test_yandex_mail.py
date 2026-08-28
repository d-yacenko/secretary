import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.connectors.yandex.constants import DEFAULT_MAIL_FOLDER
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.errors import YandexConnectorError
from app.connectors.yandex.imap_transport import FakeImapTransport
from app.connectors.yandex.mail_normalize import build_external_id, normalize_imap_message
from app.connectors.yandex.mail_sync import build_yandex_mail_sync_service
from app.db.models import Object, User, YandexMailAccount
from app.main import app
from app.users.bootstrap import BOOTSTRAP_USER_ID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_raw_email(
    subject: str = "Yandex test",
    body: str = "Hello from Yandex",
    message_id: str = "<msg@yandex.test>",
) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "sender@yandex.ru"
    msg["To"] = "user@yandex.ru"
    msg["Message-ID"] = message_id
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.set_content(body)
    return msg.as_bytes()


@pytest.fixture
def credential_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_normalize_imap_message_matches_email_object_shape() -> None:
    raw = _build_raw_email()
    normalized = normalize_imap_message(raw, folder=DEFAULT_MAIL_FOLDER, uid=42, uidvalidity=7)
    assert normalized["kind"] == "email"
    assert normalized["provider"] == "yandex_mail"
    assert normalized["origin"] == "source"
    assert normalized["state"] == "observed"
    assert normalized["external_id"] == build_external_id(DEFAULT_MAIL_FOLDER, 7, 42)
    assert normalized["body"] == "Hello from Yandex"
    assert normalized["metadata"]["imap_uid"] == 42
    assert normalized["metadata"]["imap_uidvalidity"] == 7


def test_bounded_yandex_sync_creates_observed_email_objects(
    db_session, credential_key: str
) -> None:
    store = YandexMailAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="user@yandex.ru",
        app_password="app-password",
        imap_host="imap.yandex.ru",
        imap_port=993,
    )
    db_session.commit()

    transport = FakeImapTransport(
        uidvalidity=10,
        messages={
            1: _build_raw_email(subject="First", body="Body one"),
            2: _build_raw_email(subject="Second", body="Body two"),
        },
    )

    sync_service = build_yandex_mail_sync_service(
        session=db_session,
        credential_key=credential_key,
        sync_days=30,
        default_limit=50,
        max_limit=100,
        transport_factory=lambda account, password: transport,
    )
    result = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=10)

    assert result["created"] == 2
    assert result["jobs_enqueued"] == 2

    objects = list(
        db_session.scalars(
            select(Object).where(
                Object.provider == "yandex_mail",
                Object.kind == "email",
            )
        ).all()
    )
    assert len(objects) == 2
    for obj in objects:
        assert obj.user_id == BOOTSTRAP_USER_ID
        assert obj.origin == "source"
        assert obj.state == "observed"


def test_second_yandex_sync_skips_fetch_for_known_ids(
    db_session, credential_key: str
) -> None:
    store = YandexMailAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="owner@yandex.ru",
        app_password="app-password",
        imap_host="imap.yandex.ru",
        imap_port=993,
    )
    db_session.commit()

    transport = FakeImapTransport(
        uidvalidity=5,
        messages={100: _build_raw_email(subject="Known", body="Stable body")},
    )
    sync_service = build_yandex_mail_sync_service(
        session=db_session,
        credential_key=credential_key,
        sync_days=30,
        default_limit=50,
        max_limit=100,
        transport_factory=lambda account, password: transport,
    )
    first = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=5)
    second = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=5)

    assert first["created"] == 1
    assert first["jobs_enqueued"] == 1
    assert transport.fetch_calls == [100]
    assert second["created"] == 0
    assert second["unchanged"] == 1
    assert second["jobs_enqueued"] == 0
    assert transport.fetch_calls == [100]


def test_user_b_cannot_sync_user_a_yandex_account(db_session, credential_key: str) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    store = YandexMailAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="owner@yandex.ru",
        app_password="app-password",
        imap_host="imap.yandex.ru",
        imap_port=993,
    )
    db_session.commit()

    sync_service = build_yandex_mail_sync_service(
        session=db_session,
        credential_key=credential_key,
        sync_days=30,
        default_limit=50,
        max_limit=100,
        transport_factory=lambda account, password: FakeImapTransport(messages={1: _build_raw_email()}),
    )
    with pytest.raises(YandexConnectorError, match="yandex mail account not found"):
        sync_service.sync_account(account.id, user_b_id, limit=1)


def test_two_users_can_store_same_yandex_external_id(
    db_session, credential_key: str
) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    for user_id in (BOOTSTRAP_USER_ID, user_b_id):
        store = YandexMailAccountStore(db_session, CredentialEncryption(credential_key))
        account = store.upsert_account(
            user_id=user_id,
            email=f"{user_id}@yandex.ru",
            app_password="app-password",
            imap_host="imap.yandex.ru",
            imap_port=993,
        )
        db_session.flush()
        transport = FakeImapTransport(
            uidvalidity=3,
            messages={50: _build_raw_email(subject=f"For {user_id}")},
        )
        sync_service = build_yandex_mail_sync_service(
            session=db_session,
            credential_key=credential_key,
            sync_days=30,
            default_limit=50,
            max_limit=100,
            transport_factory=lambda account, password: transport,
        )
        sync_service.sync_account(account.id, user_id, limit=1)

    external_id = build_external_id(DEFAULT_MAIL_FOLDER, 3, 50)
    objs = list(
        db_session.scalars(
            select(Object).where(
                Object.provider == "yandex_mail",
                Object.external_id == external_id,
            )
        ).all()
    )
    assert len(objs) == 2
    assert {obj.user_id for obj in objs} == {BOOTSTRAP_USER_ID, user_b_id}


def test_yandex_connect_api_does_not_return_app_password(
    client, db_session, credential_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "secretary_credential_key", credential_key)
    response = client.post(
        "/connectors/yandex/mail/connect",
        json={
            "email": "api@yandex.ru",
            "app_password": "secret-app-password",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "api@yandex.ru"
    assert "app_password" not in body
    assert "secret-app-password" not in response.text

    account = db_session.scalar(
        select(YandexMailAccount).where(YandexMailAccount.email == "api@yandex.ru")
    )
    assert account is not None
    assert account.user_id == BOOTSTRAP_USER_ID
