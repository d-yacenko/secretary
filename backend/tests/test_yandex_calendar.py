import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_db
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.calendar_normalize import (
    build_external_id,
    normalize_caldav_event,
    normalize_caldav_events,
)
from app.connectors.yandex.calendar_sync import build_yandex_calendar_sync_service
from app.connectors.yandex.caldav_transport import (
    CalDavCalendar,
    CalDavEvent,
    CalDavFetchResult,
    CalDavHttpTransport,
    FakeCalDavTransport,
)
from app.connectors.yandex.errors import YandexCalDavError, YandexConnectorError
from app.db.models import Object, User, YandexCalendarAccount
from app.main import app
from app.users.bootstrap import BOOTSTRAP_USER_ID


CALENDAR_HREF = "/calendars/user@yandex.ru/events-1/"
PRINCIPAL_HREF = "/principals/users/user@yandex.ru/"
HOME_HREF = "/calendars/user@yandex.ru/"
SHARED_EVENT_UID = "shared-corporate-evt"


def _sample_ical(
    event_uid: str = "evt-yandex-1",
    summary: str = "Standup",
    description: str = "Daily sync",
    dtstart: str = "20260829T100000Z",
    dtend: str = "20260829T110000Z",
    recurrence_id: str | None = None,
) -> str:
    recurrence_line = f"RECURRENCE-ID:{recurrence_id}\n" if recurrence_id else ""
    return (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        f"UID:{event_uid}\n"
        f"{recurrence_line}"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        "LOCATION:Room B\n"
        "STATUS:CONFIRMED\n"
        "LAST-MODIFIED:20260828T080000Z\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )


def _event(
    event_uid: str,
    summary: str = "Standup",
    description: str = "Daily sync",
    dtstart: str = "20260829T100000Z",
    dtend: str = "20260829T110000Z",
    recurrence_id: str | None = None,
) -> CalDavEvent:
    return CalDavEvent(
        event_href=f"{CALENDAR_HREF}{event_uid}.ics",
        etag=f'"{event_uid}"',
        calendar_data=_sample_ical(
            event_uid,
            summary,
            description,
            dtstart,
            dtend,
            recurrence_id,
        ),
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
    assert normalized["external_id"] == build_external_id(CALENDAR_HREF, "evt-yandex-1")


def test_normalize_moscow_tzid_to_utc() -> None:
    ical = (
        "BEGIN:VEVENT\n"
        "UID:tz-test\n"
        "DTSTART;TZID=Europe/Moscow:20260829T100000\n"
        "DTEND;TZID=Europe/Moscow:20260829T110000\n"
        "END:VEVENT\n"
    )
    events = normalize_caldav_events(ical, CALENDAR_HREF)
    assert len(events) == 1
    assert events[0]["start_at"] == datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc)


def test_normalize_recurring_occurrences_have_distinct_external_ids() -> None:
    ical = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        "UID:weekly-1\n"
        "RECURRENCE-ID:20260829T100000Z\n"
        "SUMMARY:Week 1\n"
        "DTSTART:20260829T100000Z\n"
        "DTEND:20260829T110000Z\n"
        "END:VEVENT\n"
        "BEGIN:VEVENT\n"
        "UID:weekly-1\n"
        "RECURRENCE-ID:20260905T100000Z\n"
        "SUMMARY:Week 2\n"
        "DTSTART:20260905T100000Z\n"
        "DTEND:20260905T110000Z\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )
    events = normalize_caldav_events(ical, CALENDAR_HREF)
    assert len(events) == 2
    ids = {event["external_id"] for event in events}
    assert len(ids) == 2


def test_normalize_filters_occurrences_outside_window() -> None:
    ical = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        "UID:out-window\n"
        "SUMMARY:Old\n"
        "DTSTART:20200101T100000Z\n"
        "DTEND:20200101T110000Z\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )
    time_min = datetime(2026, 1, 1, tzinfo=timezone.utc)
    time_max = datetime(2026, 12, 31, tzinfo=timezone.utc)
    events = normalize_caldav_events(
        ical,
        CALENDAR_HREF,
        time_min=time_min,
        time_max=time_max,
    )
    assert events == []


class DiscoveryHttpClient:
    def __init__(self, principal_xml: str, home_xml: str) -> None:
        self._principal_xml = principal_xml
        self._home_xml = home_xml
        self.requests: list[tuple[str, str, str]] = []

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        depth = kwargs.get("headers", {}).get("Depth", "0")
        path = url.split("caldav.yandex.ru", 1)[-1]
        self.requests.append((method, path, depth))
        if PRINCIPAL_HREF in path:
            return httpx.Response(200, text=self._principal_xml)
        if HOME_HREF in path:
            return httpx.Response(200, text=self._home_xml)
        raise AssertionError(f"unexpected request {method} {url}")


def test_caldav_discovery_uses_principal_then_calendar_home() -> None:
    principal_xml = (
        "<d:multistatus xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
        "<d:response><d:href>" + PRINCIPAL_HREF + "</d:href>"
        "<d:propstat><d:prop><c:calendar-home-set><d:href>" + HOME_HREF + "</d:href>"
        "</c:calendar-home-set></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "</d:response></d:multistatus>"
    )
    home_xml = (
        "<d:multistatus xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
        "<d:response><d:href>" + HOME_HREF + "</d:href>"
        "<d:propstat><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        "<d:response><d:href>" + CALENDAR_HREF + "</d:href>"
        "<d:propstat><d:prop><d:displayname>Work</d:displayname>"
        "<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>"
        "<d:sync-token>token-home</d:sync-token></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        "</d:multistatus>"
    )
    http = DiscoveryHttpClient(principal_xml, home_xml)
    transport = CalDavHttpTransport(
        email="user@yandex.ru",
        password="pass",
        http_client=http,
    )
    calendars = transport.discover_calendars(10)
    assert len(calendars) == 1
    assert calendars[0].href == CALENDAR_HREF
    assert http.requests[0] == ("PROPFIND", PRINCIPAL_HREF, "0")
    assert http.requests[1] == ("PROPFIND", HOME_HREF, "1")


def test_sync_collection_uses_depth_zero() -> None:
    captured: dict[str, str] = {}

    class SyncHttpClient:
        def request(self, method: str, url: str, **kwargs) -> httpx.Response:
            captured["depth"] = kwargs["headers"]["Depth"]
            xml = (
                "<d:multistatus xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
                "<d:sync-token>token-next</d:sync-token></d:multistatus>"
            )
            return httpx.Response(200, text=xml)

    transport = CalDavHttpTransport(
        email="user@yandex.ru",
        password="pass",
        http_client=SyncHttpClient(),
    )
    transport.sync_collection(CALENDAR_HREF, "token-start", 100)
    assert captured["depth"] == "0"


def test_sync_collection_batches_with_partial_tokens(db_session, credential_key: str) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="batch@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    store.update_sync_state(
        account,
        {"calendars": {CALENDAR_HREF: {"sync_token": "token-start"}}},
    )
    db_session.commit()

    all_events = [_event(f"evt-{index}") for index in range(250)]
    batches: dict[str, CalDavFetchResult] = {
        "token-start": CalDavFetchResult(
            events=all_events[0:100],
            sync_token="token-100",
        ),
        "token-100": CalDavFetchResult(
            events=all_events[100:200],
            sync_token="token-200",
        ),
        "token-200": CalDavFetchResult(
            events=all_events[200:250],
            sync_token="token-final",
        ),
    }
    transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="token-start")],
        sync_batches_by_calendar={CALENDAR_HREF: batches},
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

    first = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=100)
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    assert first["created"] == 100
    assert account.sync_state["calendars"][CALENDAR_HREF]["sync_token"] == "token-100"

    second = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=100)
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    assert second["created"] == 100
    assert account.sync_state["calendars"][CALENDAR_HREF]["sync_token"] == "token-200"

    third = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=100)
    account = store.get_by_id_for_user(account.id, BOOTSTRAP_USER_ID)
    assert third["created"] == 50
    assert account.sync_state["calendars"][CALENDAR_HREF]["sync_token"] == "token-final"

    count = db_session.scalar(
        select(func.count()).select_from(Object).where(Object.provider == "yandex_calendar")
    )
    assert count == 250


def test_sync_collection_tombstones_deleted_event(db_session, credential_key: str) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="delete@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    event = _event("evt-delete")
    create_transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="t1")],
        query_events_by_calendar={CALENDAR_HREF: [event]},
        sync_tokens_by_calendar={CALENDAR_HREF: "t2"},
    )
    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=lambda snapshot: create_transport,
    )
    sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)
    obj = db_session.scalar(
        select(Object).where(
            Object.external_id == build_external_id(CALENDAR_HREF, "evt-delete")
        )
    )
    assert obj is not None

    delete_transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="t2")],
        sync_batches_by_calendar={
            CALENDAR_HREF: {
                "t2": CalDavFetchResult(
                    events=[],
                    sync_token="t3",
                    deleted_hrefs=[event.event_href],
                )
            }
        },
    )
    sync_service = build_yandex_calendar_sync_service(
        session=db_session,
        credential_key=credential_key,
        days_back=60,
        days_forward=90,
        default_limit=100,
        max_limit=100,
        max_calendars=10,
        transport_factory=lambda snapshot: delete_transport,
    )
    result = sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)
    assert result["tombstoned"] == 1
    obj = db_session.scalar(select(Object).where(Object.id == obj.id))
    assert obj.status == "deleted"
    assert obj.metadata_["caldav_deleted"] is True


def test_no_db_transaction_during_caldav_network(db_session, credential_key: str) -> None:
    store = YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key))
    account = store.upsert_account(
        user_id=BOOTSTRAP_USER_ID,
        email="tx@yandex.ru",
        app_password="calendar-app-password",
        caldav_host="caldav.yandex.ru",
    )
    db_session.commit()

    transport = FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="Work", sync_token="t1")],
        query_events_by_calendar={CALENDAR_HREF: [_event("evt-tx")]},
        tx_checker=lambda: db_session.in_transaction(),
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
    sync_service.sync_account(account.id, BOOTSTRAP_USER_ID, limit=1)
    assert transport.discover_calls == 1
    assert transport.query_calls == [CALENDAR_HREF]


def test_malformed_caldav_xml_raises_controlled_error() -> None:
    transport = CalDavHttpTransport(email="user@yandex.ru", password="pass")
    with pytest.raises(YandexCalDavError, match="xml malformed"):
        transport._parse_event_multistatus("<not-xml")


def test_parse_multistatus_uses_ok_propstat_when_multiple_present() -> None:
    xml = (
        "<d:multistatus xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:caldav'>"
        "<d:response><d:href>" + CALENDAR_HREF + "evt.ics</d:href>"
        "<d:propstat><d:status>HTTP/1.1 404 Not Found</d:status></d:propstat>"
        "<d:propstat><d:prop><d:getetag>\"e1\"</d:getetag>"
        "<c:calendar-data>BEGIN:VEVENT\nUID:multi-prop\nEND:VEVENT</c:calendar-data>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "</d:response></d:multistatus>"
    )
    transport = CalDavHttpTransport(email="user@yandex.ru", password="pass")
    events, token, deleted = transport._parse_event_multistatus(xml)
    assert len(events) == 1
    assert "UID:multi-prop" in events[0].calendar_data


def test_sync_collection_raises_when_fake_exceeds_limit() -> None:
    transport = FakeCalDavTransport(
        sync_batches_by_calendar={
            CALENDAR_HREF: {
                "token-start": CalDavFetchResult(
                    events=[_event(f"evt-{i}") for i in range(101)],
                    sync_token="token-next",
                )
            }
        },
    )
    with pytest.raises(YandexCalDavError, match="exceeded requested result limit"):
        transport.sync_collection(CALENDAR_HREF, "token-start", 100)


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

    obj = db_session.scalar(
        select(Object).where(
            Object.provider == "yandex_calendar",
            Object.external_id == build_external_id(CALENDAR_HREF, "evt-yandex-1"),
        )
    )
    assert obj is not None
    assert obj.user_id == BOOTSTRAP_USER_ID


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
        sync_batches_by_calendar={
            CALENDAR_HREF: {
                "token-2": CalDavFetchResult(
                    events=[_event("evt-yandex-2")],
                    sync_token="token-3",
                )
            }
        },
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
    assert second["unchanged"] == 1
    assert second["jobs_enqueued"] == 0
    assert transport.sync_collection_calls == [(CALENDAR_HREF, "token-2", 1)]


def test_two_users_share_same_external_id_under_different_user_id(
    db_session, credential_key: str
) -> None:
    user_b_id = uuid.uuid4()
    db_session.add(User(id=user_b_id, display_name="User B"))
    db_session.flush()
    shared_external_id = build_external_id(CALENDAR_HREF, SHARED_EVENT_UID)

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
            query_events_by_calendar={
                CALENDAR_HREF: [_event(SHARED_EVENT_UID, summary=str(user_id))]
            },
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

    objs = list(
        db_session.scalars(
            select(Object).where(
                Object.provider == "yandex_calendar",
                Object.external_id == shared_external_id,
            )
        ).all()
    )
    assert len(objs) == 2
    assert {obj.user_id for obj in objs} == {BOOTSTRAP_USER_ID, user_b_id}


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
