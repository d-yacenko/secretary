from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.yandex.calendar_credentials import (
    YandexCalendarAccountStore,
    YandexCalendarSyncSnapshot,
)
from app.connectors.yandex.calendar_normalize import normalize_caldav_events
from app.connectors.yandex.caldav_transport import CalDavFetchResult, CalDavHttpTransport, CalDavTransport
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


@dataclass
class _BatchStats:
    synchronized: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    tombstoned: int = 0
    jobs_enqueued: int = 0


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

        occurrence_budget = limit if limit is not None else self._default_limit
        occurrence_budget = min(max(occurrence_budget, 1), self._max_limit)

        self._session.commit()

        transport = self._open_transport(snapshot)
        time_min = utcnow() - timedelta(days=self._days_back)
        time_max = utcnow() + timedelta(days=self._days_forward)
        calendars = transport.discover_calendars(self._max_calendars)

        totals = _BatchStats()
        calendar_state = dict(snapshot.sync_state.get("calendars", {}))

        for calendar in calendars:
            if occurrence_budget <= 0:
                break

            calendar_href = calendar.href
            stored = dict(calendar_state.get(calendar_href, {}))
            stored_token = stored.get("sync_token")
            calendar_summary = calendar.display_name or stored.get("display_name")

            if stored_token:
                batch_stats, occurrence_budget, stored = self._sync_incremental_calendar(
                    transport=transport,
                    snapshot=snapshot,
                    calendar_href=calendar_href,
                    stored=stored,
                    stored_token=str(stored_token),
                    calendar_summary=calendar_summary,
                    time_min=time_min,
                    time_max=time_max,
                    occurrence_budget=occurrence_budget,
                )
            else:
                self._session.commit()
                fetch_result = transport.query_events(
                    calendar_href=calendar_href,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=self._max_limit,
                )
                batch_stats = self._apply_fetch_batch(
                    user_id=snapshot.user_id,
                    fetch_result=fetch_result,
                    calendar_href=calendar_href,
                    calendar_summary=calendar_summary,
                    time_min=time_min,
                    time_max=time_max,
                    cap_occurrences=True,
                    occurrence_budget=occurrence_budget,
                )
                occurrence_budget -= batch_stats.synchronized
                if fetch_result.sync_token:
                    stored["sync_token"] = fetch_result.sync_token
                elif calendar.sync_token:
                    stored["sync_token"] = calendar.sync_token

            self._merge_stats(totals, batch_stats)
            if calendar_summary:
                stored["display_name"] = calendar_summary
            calendar_state[calendar_href] = stored

        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise YandexConnectorError("yandex calendar account not found")
        self._account_store.update_sync_state(account, {"calendars": calendar_state})
        self._session.commit()

        return {
            "account_email": snapshot.email,
            "synchronized": totals.synchronized,
            "created": totals.created,
            "updated": totals.updated,
            "unchanged": totals.unchanged,
            "tombstoned": totals.tombstoned,
            "jobs_enqueued": totals.jobs_enqueued,
        }

    def _sync_incremental_calendar(
        self,
        transport: CalDavTransport,
        snapshot: YandexCalendarSyncSnapshot,
        calendar_href: str,
        stored: dict[str, Any],
        stored_token: str,
        calendar_summary: str | None,
        time_min: datetime,
        time_max: datetime,
        occurrence_budget: int,
    ) -> tuple[_BatchStats, int, dict[str, Any]]:
        totals = _BatchStats()
        current_token = stored_token

        while True:
            if occurrence_budget <= 0:
                break
            self._session.commit()
            try:
                fetch_result = transport.sync_collection(
                    calendar_href=calendar_href,
                    sync_token=current_token,
                    max_results=self._max_limit,
                    time_min=time_min,
                    time_max=time_max,
                )
            except YandexConnectorError:
                self._session.commit()
                fetch_result = transport.query_events(
                    calendar_href=calendar_href,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=self._max_limit,
                )
                batch_stats = self._apply_fetch_batch(
                    user_id=snapshot.user_id,
                    fetch_result=fetch_result,
                    calendar_href=calendar_href,
                    calendar_summary=calendar_summary,
                    time_min=time_min,
                    time_max=time_max,
                    cap_occurrences=True,
                    occurrence_budget=occurrence_budget,
                )
                self._merge_stats(totals, batch_stats)
                occurrence_budget -= batch_stats.synchronized
                if fetch_result.sync_token:
                    stored["sync_token"] = fetch_result.sync_token
                return totals, occurrence_budget, stored

            batch_stats = self._apply_fetch_batch(
                user_id=snapshot.user_id,
                fetch_result=fetch_result,
                calendar_href=calendar_href,
                calendar_summary=calendar_summary,
                time_min=time_min,
                time_max=time_max,
                cap_occurrences=False,
                occurrence_budget=occurrence_budget,
            )
            self._merge_stats(totals, batch_stats)
            occurrence_budget -= batch_stats.synchronized

            if fetch_result.sync_token:
                stored["sync_token"] = fetch_result.sync_token

            if not fetch_result.events:
                break
            if fetch_result.sync_token is None:
                break
            if not fetch_result.truncated and fetch_result.sync_token == current_token:
                break
            current_token = fetch_result.sync_token
            if occurrence_budget <= 0:
                break

        return totals, occurrence_budget, stored

    def _apply_fetch_batch(
        self,
        user_id: UUID,
        fetch_result: CalDavFetchResult,
        calendar_href: str,
        calendar_summary: str | None,
        time_min: datetime,
        time_max: datetime,
        cap_occurrences: bool,
        occurrence_budget: int,
    ) -> _BatchStats:
        stats = _BatchStats()

        for deleted_href in fetch_result.deleted_hrefs:
            self._session.commit()
            tombstoned_count = self._tombstone_all_by_event_href(user_id, deleted_href)
            stats.tombstoned += tombstoned_count
            stats.synchronized += tombstoned_count
            self._session.commit()

        for raw_event in fetch_result.events:
            normalized_list = normalize_caldav_events(
                raw_event.calendar_data,
                calendar_href=calendar_href,
                calendar_summary=calendar_summary,
                etag=raw_event.etag,
                event_href=raw_event.event_href,
                time_min=time_min,
                time_max=time_max,
            )
            for normalized in normalized_list:
                if cap_occurrences and occurrence_budget <= 0:
                    break
                change = self._upsert_event(user_id, normalized)
                stats.synchronized += 1
                if cap_occurrences:
                    occurrence_budget -= 1
                if change == "created":
                    stats.created += 1
                    stats.jobs_enqueued += 1
                elif change == "updated":
                    stats.updated += 1
                    stats.jobs_enqueued += 1
                else:
                    stats.unchanged += 1
                self._session.commit()
            if cap_occurrences and occurrence_budget <= 0:
                break

        return stats

    def _merge_stats(self, totals: _BatchStats, batch: _BatchStats) -> None:
        totals.synchronized += batch.synchronized
        totals.created += batch.created
        totals.updated += batch.updated
        totals.unchanged += batch.unchanged
        totals.tombstoned += batch.tombstoned
        totals.jobs_enqueued += batch.jobs_enqueued

    def _upsert_event(self, user_id: UUID, normalized: dict[str, Any]) -> str:
        existing = self._find_existing_event(user_id, normalized["external_id"])
        if existing is None:
            obj = Object(
                user_id=user_id,
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
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(obj.id)},
                user_id=user_id,
            )
            return "created"

        if self._event_changed(existing, normalized):
            self._apply_normalized_event(existing, normalized)
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(existing.id)},
                user_id=user_id,
            )
            return "updated"
        return "unchanged"

    def _tombstone_all_by_event_href(self, user_id: UUID, event_href: str) -> int:
        tombstoned = 0
        for obj in self._find_all_by_event_href(user_id, event_href):
            if obj.status == "deleted":
                continue
            metadata = dict(obj.metadata_ or {})
            metadata["caldav_deleted"] = True
            metadata["deleted_at"] = utcnow().isoformat()
            obj.status = "deleted"
            obj.metadata_ = metadata
            tombstoned += 1
        return tombstoned

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

    def _find_all_by_event_href(self, user_id: UUID, event_href: str) -> list[Object]:
        return list(
            self._session.scalars(
                select(Object).where(
                    Object.user_id == user_id,
                    Object.provider == "yandex_calendar",
                    Object.kind == "event",
                    Object.metadata_["event_href"].as_string() == event_href,
                )
            ).all()
        )

    def _event_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.status == "deleted":
            return True
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
        obj.status = None


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
