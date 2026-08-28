import uuid
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_db
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.calendar_normalize import build_external_id, normalize_caldav_event
from app.connectors.yandex.calendar_sync import build_yandex_calendar_sync_service
from app.connectors.yandex.caldav_transport import CalDavCalendar, CalDavEvent, FakeCalDavTransport
from app.connectors.yandex.errors import YandexConnectorError
from app.db.models import Object, User, YandexCalendarAccount
from app.main import app
from app.users.bootstrap import BOOTSTRAP_USER_ID


CALENDAR_HREF = "/calendars/user@yandex.ru/events-1/"


def _sample_ical(
    event_uid: str = "evt-yandex-1",
    summary: str = "Standup",
    description: str = "Daily sync",
) -> str:
    return (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        f"UID:{event_uid}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        "DTSTART:20260829T100000Z\n"
        "DTEND:20260829T110000Z\n"
        "LOCATION:Room B\n"
        "STATUS:CONFIRMED\n"
        "LAST-MODIFIED:20260828T080000Z\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )


def _event(event_uid: str, summary: str = "Standup", description: str = "Daily sync") -> CalDavEvent:
    return CalDavEvent(
        event_href=f"{CALENDAR_HREF}{event_uid}.ics",
        etag=f'"{event_uid}"',
        calendar_data=_sample_ical(event_uid, summary, description),
    )


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


def test_normalize_caldav_event_matches_event_object_shape() -> None:
    normalized = normalize_caldav_event(
        _sample_ical(),
        calendar_href=CALENDAR_HREF,
        calendar_summary="Work",
        etag='"etag-1"',
        event_href=f"{CALENDAR_HREF}evt-yandex-1.ics",
    )
    assert normalized is not None
    assert normalized["kind"] == "event"
    assert normalized["provider"] == "yandex_calendar"
    assert normalized["origin"] == "source"
    assert normalized["state"] == "observed"
    assert normalized["external_id"] == build_external_id(CALENDAR_HREF, "evt-yandex-1")
    assert normalized["metadata"]["calendar_href"] == CALENDAR_HREF
    assert normalized["metadata"]["event_uid"] == "evt-yandex-1"
    assert normalized["start_at"] is not None
    assert normalized["due_at"] is not None


def test_bounded_yandex_calendar_sync_creates_observed_event_objects(
    db_session, credential_key: str
) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="user@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="token-1")],
        query_events_by_calendar={CALENDAR_HREF: [_event("evt-yandex-1")]},
        sync_tokens_by_calendar={CALENDAR_HREF: "token-1"},
    )
    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=lambda snapshot: transport,
    )
    result = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=5)

    assert result["created"] == 1
    assert result["jobs_enqueued"] == 1
    assert transport.query_calls == [CALENDAR_HREF]

    obj = db_session.scalar(
        select(Object).where(
            Object.provider == "yandex_calendar",
            Object.kind == "event",
            Object.external_id == build_external_id(CALENDAR_HREF, "evt-yandex-1"),
        )
    )
    assert obj is not None
    assert obj.user_id == BOOTSTRAP_USER_ID
    assert obj.origin == "source"
    assert obj.state == "observed"
    assert obj.title == "Standup"
    assert obj.body == "Daily sync"


def test_yandex_calendar_resync_unchanged_without_duplicate_jobs(
    db_session, credential_key: str
) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="owner@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="token-1")],
        query_events_by_calendar={CALENDAR_HREF: [_event("evt-yandex-2")]},
        sync_events_by_calendar={CALENDAR_HREF: [_event("evt-yandex-2")]},
        sync_tokens_by_calendar={CALENDAR_HREF: "token-2"},
    )
    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=lambda snapshot: transport,
    )
    first = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)
    second = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 1
    assert second["jobs_enqueued"] == 0
    assert transport.sync_collection_calls == [(CALENDAR_HREF, "token-2")]

    count = db_session.scalar(
        select(func.count())
        .select_from(Object)
        .where(
            Object.provider == "yandex_calendar",
            Object.external_id == build_external_id(CALENDAR_HREF, "evt-yandex-2"),
        )
    )
    assert count == 1


def test_yandex_calendar_resync_updates_object_on_title_change(
    db_session, credential_key: str
) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="owner@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    class TransportFactory:
        def __init__(self) -> None:
            self.call = 0

        def build(self, snapshot) -> FakeCalDavTransport:
            self.call += 1
            summary = "Standup" if self.call == 1 else "Updated title"
            event = _event("evt-yandex-upd", summary=summary)
            return FakeCalDavTransport(
                calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="t1")],
                query_events_by_calendar={CALENDAR_HREF: [event]},
                sync_events_by_calendar={CALENDAR_HREF: [event]},
                sync_tokens_by_calendar={CALENDAR_HREF: "t2"},
            )

    factory = TransportFactory()
    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=factory.build,
    )
    first = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)
    second = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)

    assert first["created"] == 1
    assert second["updated"] == 1
    assert second["jobs_enqueued"] == 1

    obj = db_session.scalar(
        select(Object).where(
            Object.external_id == build_external_id(CALENDAR_HREF, "evt-yandex-upd")
        )
    )
    assert obj is not None
    assert obj.title == "Updated title"


def test_user_b_cannot_sync_user_a_yandex_calendar_account(
    db_session, credential_key: str
) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="owner@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=lambda snapshot: FakeCalDavTransport(
            calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token=None)],
            query_events_by_calendar={CALENDAR_HREF: [_event("evt-yandex-3")]},
        ),
    )
    with pytest.raises(YandexConnectorError, match="yandex calendar account not found"):
        sync_service.sync_account(account.id, user_b_id, limit=1)


def test_two_users_can_store_same_yandex_calendar_external_id(
    db_session, credential_key: str
) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()

    for user_id in (BOOTSTRAP_USER_ID, user_b_id):
        store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
        account = store.upsert_account(
            user_id=user_id,
            email=f"{user_id}@yandex.ru",
            app_password="calendar-app-password",
            caldav_host="caldav.yandex.ru",
        )
        db_session.flush()
        transport = FakeCalDavTransport(
            calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token=None)],
            query_events_by_calendar={CALENDAR_HREF: [_event(f"evt-{user_id}", summary=str(user_id))]},
        )
        sync_service = build_yandex_calendar_sync_service(
            session=db_session,
            credential_key=credential_key,
            days_back=60,
            days_forward=90,
            default_limit=100,
            max_limit=100,
            max_calendars=10,
            transport_factory=lambda snapshot: transport,
        )
        sync_service.sync_account(account.id, user_id, limit=1)

    external_id = build_external_id(CALENDAR_HREF, f"evt-{user_b_id}")
    objs = list(
        db_session.scalars(
            select(Object).where(
                Object.provider == "yandex_calendar",
                Object.external_id == external_id,
            )
        ).all()
    )
    assert len(objs) == 1
    assert objs[0].user_id == user_b_id

    external_id_a = build_external_id(CALENDAR_HREF, f"evt-{BOOTSTRAP_USER_ID}")
    objs_a = list(
        db_session.scalars(
            select(Object).where(
                Object.provider == "yandex_calendar",
                Object.external_id == external_id_a,
            )
        ).all()
    )
    assert len(objs_a) == 1
    assert objs_a[0].user_id == BOOTSTRAP_USER_ID


def test_yandex_calendar_connect_api_does_not_return_app_password(
    client, db_session, credential_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "secretary_credential_key", credential_key)
    response = client.post(
        "/connectors/yandex/calendar/connect",
        json={
            "email": "calendar@yandex.ru",
            "app_password": "secret-calendar-password",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "calendar@yandex.ru"
    assert "app_password" not in body
    assert "secret-calendar-password" not in response.text

    account = db_session.scalar(
        select(YandexCalendarAccount).where(YandexCalendarAccount.email == "calendar@yandex.ru")
    )
    assert account is not None
    assert account.user_id == BOOTSTRAP_USER_ID
