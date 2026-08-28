from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.yandex.calendar_credentials import (
    YandexCalendarAccountStore,
    YandexCalendarSyncSnapshot,
)
from app.connectors.yandex.calendar_normalize import normalize_caldav_event
from app.connectors.yandex.caldav_transport import CalDavHttpTransport, CalDavTransport
from app.connectors.yandex.constants import (
    DEFAULT_CALENDAR_SYNC_DAYS_BACK,
    DEFAULT_CALENDAR_SYNC_DAYS_FORWARD,
    DEFAULT_CALENDAR_SYNC_LIMIT,
    MAX_CALENDAR_SYNC_CALENDARS,
    MAX_CALENDAR_SYNC_DAYS_BACK,
    MAX_CALENDAR_SYNC_DAYS_FORWARD,
    MAX_CALENDAR_SYNC_LIMIT,
)
from app.connectors.yandex.errors import YandexConnectorError
from app.db.models import Object
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class YandexCalendarSyncService:
    def __init__(
        self,
        session: Session,
        account_store: YandexCalendarAccountStore,
        job_queue: JobQueueService,
        days_back: int = DEFAULT_CALENDAR_SYNC_DAYS_BACK,
        days_forward: int = DEFAULT_CALENDAR_SYNC_DAYS_FORWARD,
        default_limit: int = DEFAULT_CALENDAR_SYNC_LIMIT,
        max_limit: int = MAX_CALENDAR_SYNC_LIMIT,
        max_calendars: int = MAX_CALENDAR_SYNC_CALENDARS,
        transport_factory: Callable[[YandexCalendarSyncSnapshot], CalDavTransport] | None = None,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._job_queue = job_queue
        self._days_back = min(max(days_back, 1), MAX_CALENDAR_SYNC_DAYS_BACK)
        self._days_forward = min(max(days_forward, 1), MAX_CALENDAR_SYNC_DAYS_FORWARD)
        self._default_limit = default_limit
        self._max_limit = max_limit
        self._max_calendars = max_calendars
        self._transport_factory = transport_factory

    def sync_account(
        self,
        account_id: UUID,
        user_id: UUID,
        limit: int | None = None,
    ) -> dict[str, Any]:
        snapshot = self._account_store.load_sync_snapshot(account_id, user_id)
        if snapshot is None:
            raise YandexConnectorError("yandex calendar account not found")

        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(effective_limit, 1), self._max_limit)

        self._session.commit()

        transport = self._open_transport(snapshot)
        time_min = utcnow() - timedelta(days=self._days_back)
        time_max = utcnow() + timedelta(days=self._days_forward)
        calendars = transport.discover_calendars(self._max_calendars)

        created = 0
        updated = 0
        jobs_enqueued = 0
        synchronized = 0
        unchanged = 0
        remaining = effective_limit
        calendar_state = dict(snapshot.sync_state.get("calendars", {}))

        for calendar in calendars:
            if remaining <= 0:
                break
            calendar_href = calendar.href
            stored = dict(calendar_state.get(calendar_href, {}))
            stored_token = stored.get("sync_token")
            calendar_summary = calendar.display_name or stored.get("display_name")

            try:
                if stored_token:
                    fetch_result = transport.sync_collection(
                        calendar_href=calendar_href,
                        sync_token=str(stored_token),
                        max_results=remaining,
                    )
                else:
                    fetch_result = transport.query_events(
                        calendar_href=calendar_href,
                        time_min=time_min,
                        time_max=time_max,
                        max_results=remaining,
                    )
            except YandexConnectorError:
                fetch_result = transport.query_events(
                    calendar_href=calendar_href,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=remaining,
                )
                stored_token = None

            new_token = fetch_result.sync_token or stored_token or calendar.sync_token
            if new_token:
                stored["sync_token"] = new_token
            if calendar_summary:
                stored["display_name"] = calendar_summary
            calendar_state[calendar_href] = stored

            for raw_event in fetch_result.events:
                if remaining <= 0:
                    break
                normalized = normalize_caldav_event(
                    raw_event.calendar_data,
                    calendar_href=calendar_href,
                    calendar_summary=calendar_summary,
                    etag=raw_event.etag,
                    event_href=raw_event.event_href,
                )
                if normalized is None:
                    continue

                existing = self._find_existing_event(snapshot.user_id, normalized["external_id"])
                if existing is None:
                    self._session.commit()
                    obj = Object(
                        user_id=snapshot.user_id,
                        kind=normalized["kind"],
                        provider=normalized["provider"],
                        external_id=normalized["external_id"],
                        origin=normalized["origin"],
                        state=normalized["state"],
                        title=normalized["title"],
                        body=normalized.get("body"),
                        start_at=normalized.get("start_at"),
                        due_at=normalized.get("due_at"),
                        metadata_=normalized["metadata"],
                    )
                    self._session.add(obj)
                    self._session.flush()
                    created += 1
                    synchronized += 1
                    remaining -= 1
                    self._job_queue.enqueue(
                        "embed_object",
                        {"object_id": str(obj.id)},
                        user_id=snapshot.user_id,
                    )
                    jobs_enqueued += 1
                    self._session.commit()
                    continue

                if self._event_changed(existing, normalized):
                    self._apply_normalized_event(existing, normalized)
                    updated += 1
                    synchronized += 1
                    remaining -= 1
                    self._job_queue.enqueue(
                        "embed_object",
                        {"object_id": str(existing.id)},
                        user_id=snapshot.user_id,
                    )
                    jobs_enqueued += 1
                    self._session.commit()
                else:
                    synchronized += 1
                    unchanged += 1
                    remaining -= 1
                    self._session.commit()

        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise YandexConnectorError("yandex calendar account not found")
        self._account_store.update_sync_state(account, {"calendars": calendar_state})
        self._session.commit()

        return {
            "account_email": snapshot.email,
            "synchronized": synchronized,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "jobs_enqueued": jobs_enqueued,
        }

    def _open_transport(self, snapshot: YandexCalendarSyncSnapshot) -> CalDavTransport:
        if self._transport_factory is not None:
            return self._transport_factory(snapshot)
        base_url = f"https://{snapshot.caldav_host}"
        return CalDavHttpTransport(
            email=snapshot.email,
            password=snapshot.app_password,
            base_url=base_url,
        )

    def _find_existing_event(self, user_id: UUID, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == user_id,
                Object.provider == "yandex_calendar",
                Object.kind == "event",
                Object.external_id == external_id,
            )
        )

    def _event_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.title != normalized["title"]:
            return True
        if obj.body != normalized.get("body"):
            return True
        if obj.start_at != normalized.get("start_at"):
            return True
        if obj.due_at != normalized.get("due_at"):
            return True
        if obj.metadata_ != normalized["metadata"]:
            return True
        return False

    def _apply_normalized_event(self, obj: Object, normalized: dict[str, Any]) -> None:
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.start_at = normalized.get("start_at")
        obj.due_at = normalized.get("due_at")
        obj.metadata_ = normalized["metadata"]


def build_yandex_calendar_sync_service(
    session: Session,
    credential_key: str,
    days_back: int,
    days_forward: int,
    default_limit: int,
    max_limit: int,
    max_calendars: int,
    transport_factory: Callable[[YandexCalendarSyncSnapshot], CalDavTransport] | None = None,
) -> YandexCalendarSyncService:
    account_store = YandexCalendarAccountStore(
        session,
        YandexCalendarAccountStore.build_encryption(credential_key),
    )
    job_queue = JobQueueService(session)
    return YandexCalendarSyncService(
        session=session,
        account_store=account_store,
        job_queue=job_queue,
        days_back=days_back,
        days_forward=days_forward,
        default_limit=default_limit,
        max_limit=max_limit,
        max_calendars=max_calendars,
        transport_factory=transport_factory,
    )
