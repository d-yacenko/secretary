from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.calendar_normalize import normalize_calendar_event
from app.connectors.google.calendar_transport import CalendarTransport
from app.connectors.google.constants import (
    CALENDAR_READONLY_SCOPE,
    DEFAULT_CALENDAR_SYNC_DAYS_BACK,
    DEFAULT_CALENDAR_SYNC_DAYS_FORWARD,
    DEFAULT_CALENDAR_SYNC_MAX_EVENTS,
    MAX_CALENDAR_SYNC_CALENDARS,
    MAX_CALENDAR_SYNC_EVENTS,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.errors import GoogleConnectorError
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.db.models import Object
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(UTC)


class CalendarSyncService:
    def __init__(
        self,
        session: Session,
        account_store: GoogleAccountStore,
        token_manager: GoogleTokenManager,
        transport: CalendarTransport,
        job_queue: JobQueueService,
        days_back: int = DEFAULT_CALENDAR_SYNC_DAYS_BACK,
        days_forward: int = DEFAULT_CALENDAR_SYNC_DAYS_FORWARD,
        default_limit: int = DEFAULT_CALENDAR_SYNC_MAX_EVENTS,
        max_limit: int = MAX_CALENDAR_SYNC_EVENTS,
        max_calendars: int = MAX_CALENDAR_SYNC_CALENDARS,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._token_manager = token_manager
        self._transport = transport
        self._job_queue = job_queue
        self._days_back = days_back
        self._days_forward = days_forward
        self._default_limit = default_limit
        self._max_limit = max_limit
        self._max_calendars = max_calendars

    def sync_account(
        self,
        account_id: UUID,
        user_id: UUID,
        limit: int | None = None,
    ) -> dict[str, Any]:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise GoogleConnectorError("google account not found")
        if CALENDAR_READONLY_SCOPE not in account.scopes:
            raise GoogleConnectorError("google account is missing calendar scope")

        account_email = account.email
        owner_user_id = account.user_id
        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(effective_limit, 1), self._max_limit)

        self._session.commit()
        access_token = self._token_manager.get_valid_access_token(account_id, user_id)
        self._session.commit()

        time_min = utcnow() - timedelta(days=self._days_back)
        time_max = utcnow() + timedelta(days=self._days_forward)
        calendars = self._transport.list_calendars(access_token, self._max_calendars)

        created = 0
        updated = 0
        jobs_enqueued = 0
        synchronized = 0
        unchanged = 0
        remaining = effective_limit

        for calendar in calendars:
            if remaining <= 0:
                break
            calendar_id = str(calendar.get("id", ""))
            if not calendar_id:
                continue
            calendar_summary = calendar.get("summary")
            self._session.commit()
            raw_events = self._transport.list_events(
                access_token=access_token,
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                max_results=remaining,
            )
            for raw_event in raw_events:
                if remaining <= 0:
                    break
                normalized = normalize_calendar_event(
                    raw_event,
                    calendar_id=calendar_id,
                    calendar_summary=str(calendar_summary) if calendar_summary else None,
                )
                existing = self._find_existing_calendar_object(
                    owner_user_id, normalized["external_id"]
                )

                if existing is None:
                    obj = Object(
                        user_id=owner_user_id,
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
                        user_id=owner_user_id,
                    )
                    jobs_enqueued += 1
                    self._session.commit()
                    continue

                if self._calendar_object_changed(existing, normalized):
                    self._apply_normalized_calendar_object(existing, normalized)
                    updated += 1
                    synchronized += 1
                    remaining -= 1
                    self._job_queue.enqueue(
                        "embed_object",
                        {"object_id": str(existing.id)},
                        user_id=owner_user_id,
                    )
                    jobs_enqueued += 1
                    self._session.commit()
                else:
                    synchronized += 1
                    unchanged += 1
                    remaining -= 1
                    self._session.commit()

        return {
            "account_email": account_email,
            "synchronized": synchronized,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "jobs_enqueued": jobs_enqueued,
        }

    def _find_existing_calendar_object(self, user_id: UUID, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == user_id,
                Object.provider == "google_calendar",
                Object.kind == "event",
                Object.external_id == external_id,
            )
        )

    def _calendar_object_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.title != normalized["title"]:
            return True
        if obj.body != normalized.get("body"):
            return True
        if obj.start_at != normalized.get("start_at"):
            return True
        if obj.due_at != normalized.get("due_at"):
            return True
        return obj.metadata_ != normalized["metadata"]

    def _apply_normalized_calendar_object(self, obj: Object, normalized: dict[str, Any]) -> None:
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.start_at = normalized.get("start_at")
        obj.due_at = normalized.get("due_at")
        obj.metadata_ = normalized["metadata"]


def build_calendar_sync_service(
    session: Session,
    credential_key: str,
    client_file: str,
    redirect_uri: str,
    days_back: int,
    days_forward: int,
    default_limit: int,
    max_limit: int,
    max_calendars: int,
    http_client: Any | None = None,
) -> CalendarSyncService:
    encryption = GoogleAccountStore.build_encryption(credential_key)
    account_store = GoogleAccountStore(session, encryption)
    oauth_service = GoogleOAuthService(client_file, redirect_uri, http_client=http_client)
    token_manager = GoogleTokenManager(session, account_store, oauth_service)
    transport = CalendarTransport(http_client=http_client)
    job_queue = JobQueueService(session)
    return CalendarSyncService(
        session=session,
        account_store=account_store,
        token_manager=token_manager,
        transport=transport,
        job_queue=job_queue,
        days_back=days_back,
        days_forward=days_forward,
        default_limit=default_limit,
        max_limit=max_limit,
        max_calendars=max_calendars,
    )
