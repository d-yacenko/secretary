"""Bounded Google Calendar create-event execution after approval."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.connectors.google.calendar_transport import CalendarTransport
from app.connectors.google.constants import (
    CALENDAR_EVENTS_SCOPE,
    PRIMARY_CALENDAR_ID,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.google.errors import GoogleApiError, GoogleConnectorError, GoogleOAuthError
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.core.config import settings
from app.db.models import GoogleAccount
from app.db.session import SessionLocal
from app.tools.datetime_utils import normalize_tool_datetime
from app.tools.schemas import (
    CreateCalendarEventCanonicalInput,
    CreateCalendarEventInput,
    CreateCalendarEventOutput,
    ToolError,
)

_RECONNECT_WRITE_SCOPE_MESSAGE = (
    "Google must be reconnected to grant calendar write permission"
)


def calendar_event_id_from_operation_id(operation_id: str) -> str:
    compact = operation_id.replace("-", "").lower()
    if len(compact) < 5 or len(compact) > 1024:
        raise ToolError("invalid operation_id")
    return compact


def generate_operation_id() -> str:
    return uuid4().hex


def _format_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        raise ToolError("calendar event times must be timezone-aware")
    return value.isoformat().replace("+00:00", "Z")


def _parse_provider_datetime(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # noqa: FURB162
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


class CalendarExternalActionService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        *,
        transport: CalendarTransport | None = None,
        token_session_factory=SessionLocal,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._transport = transport or CalendarTransport()
        self._token_session_factory = token_session_factory

    def prepare_create_event(
        self,
        payload: CreateCalendarEventInput,
        timezone_name: str,
    ) -> CreateCalendarEventCanonicalInput:
        start_at = normalize_tool_datetime(payload.start_at, timezone_name)
        end_at = normalize_tool_datetime(payload.end_at, timezone_name)
        if start_at is None or end_at is None:
            raise ToolError("start_at and end_at are required")
        if end_at <= start_at:
            raise ToolError("end_at must be after start_at")
        account = self._resolve_account(payload.account_email)
        self._require_write_scope(account)
        return CreateCalendarEventCanonicalInput(
            summary=payload.summary.strip(),
            start_at=start_at,
            end_at=end_at,
            description=payload.description,
            location=payload.location,
            account_email=account.email,
            calendar_id=PRIMARY_CALENDAR_ID,
            operation_id=generate_operation_id(),
        )

    def create_event(self, payload: CreateCalendarEventCanonicalInput) -> CreateCalendarEventOutput:
        if payload.calendar_id != PRIMARY_CALENDAR_ID:
            raise ToolError("calendar_id must be primary")
        account = self._resolve_account(payload.account_email)
        self._require_write_scope(account)
        event_id = calendar_event_id_from_operation_id(payload.operation_id)
        access_token = self._valid_access_token(account.id)
        body = self._provider_body(payload, event_id)
        try:
            created = self._transport.insert_event(
                access_token=access_token,
                calendar_id=PRIMARY_CALENDAR_ID,
                body=body,
            )
            self._assert_event_matches(payload, created, event_id)
            return self._output(payload, created, event_id, changed=True)
        except GoogleApiError as exc:
            if exc.status_code == 409:
                existing = self._require_matching_existing(access_token, payload, event_id)
                return self._output(payload, existing, event_id, changed=False)
            raise ToolError(self._bounded_provider_error(exc)) from exc
        except httpx.RequestError:
            return self._reconcile_after_uncertain_insert(access_token, payload, event_id)

    def _reconcile_after_uncertain_insert(
        self,
        access_token: str,
        payload: CreateCalendarEventCanonicalInput,
        event_id: str,
    ) -> CreateCalendarEventOutput:
        try:
            existing = self._get_event(access_token, event_id)
        except ToolError as exc:
            raise ToolError(
                "could not confirm calendar event creation; not retrying with a new event id"
            ) from exc
        if existing is None:
            raise ToolError("failed to create calendar event")
        self._assert_event_matches(payload, existing, event_id)
        return self._output(payload, existing, event_id, changed=False)

    def _require_matching_existing(
        self,
        access_token: str,
        payload: CreateCalendarEventCanonicalInput,
        event_id: str,
    ) -> dict[str, Any]:
        existing = self._get_event(access_token, event_id)
        if existing is None:
            raise ToolError("failed to create calendar event")
        self._assert_event_matches(payload, existing, event_id)
        return existing

    def _get_event(self, access_token: str, event_id: str) -> dict[str, Any] | None:
        try:
            return self._transport.get_event(
                access_token=access_token,
                calendar_id=PRIMARY_CALENDAR_ID,
                event_id=event_id,
            )
        except GoogleApiError as exc:
            if exc.status_code == 404:
                return None
            raise ToolError(self._bounded_provider_error(exc)) from exc
        except httpx.RequestError as exc:
            raise ToolError(
                "could not confirm calendar event creation; not retrying with a new event id"
            ) from exc

    def _valid_access_token(self, account_id: UUID) -> str:
        if not settings.secretary_credential_key:
            raise ToolError("google credentials are not configured")
        token_session = self._token_session_factory()
        try:
            store = GoogleAccountStore(
                token_session,
                GoogleAccountStore.build_encryption(settings.secretary_credential_key),
            )
            oauth_service = GoogleOAuthService(
                client_file=settings.google_oauth_client_file,
                redirect_uri=settings.google_redirect_uri,
            )
            token_manager = GoogleTokenManager(token_session, store, oauth_service)
            return token_manager.get_valid_access_token(account_id, self._user_id)
        except (GoogleConnectorError, GoogleOAuthError) as exc:
            raise ToolError(exc.message) from exc
        finally:
            token_session.close()

    def _resolve_account(self, account_email: str | None) -> GoogleAccount:
        store = self._account_store()
        accounts = store.list_accounts(self._user_id)
        if account_email:
            normalized = account_email.strip().lower()
            matches = [account for account in accounts if account.email.lower() == normalized]
            if len(matches) != 1:
                raise ToolError("Google account is not connected")
            return matches[0]
        if not accounts:
            raise ToolError("Google account is not connected")
        if len(accounts) > 1:
            raise ToolError("multiple Google accounts are connected; specify account")
        return accounts[0]

    def _require_write_scope(self, account: GoogleAccount) -> None:
        scopes = {str(scope) for scope in (account.scopes or [])}
        if CALENDAR_EVENTS_SCOPE not in scopes:
            raise ToolError(_RECONNECT_WRITE_SCOPE_MESSAGE)

    def _account_store(self) -> GoogleAccountStore:
        if not settings.secretary_credential_key:
            raise ToolError("google credentials are not configured")
        encryption = CredentialEncryption(settings.secretary_credential_key)
        return GoogleAccountStore(self._session, encryption)

    def _provider_body(
        self,
        payload: CreateCalendarEventCanonicalInput,
        event_id: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": event_id,
            "summary": payload.summary,
            "start": {"dateTime": _format_rfc3339(payload.start_at)},
            "end": {"dateTime": _format_rfc3339(payload.end_at)},
        }
        if payload.description:
            body["description"] = payload.description
        if payload.location:
            body["location"] = payload.location
        return body

    def _assert_event_matches(
        self,
        payload: CreateCalendarEventCanonicalInput,
        event: dict[str, Any],
        event_id: str,
    ) -> None:
        if str(event.get("id") or "") != event_id:
            raise ToolError("calendar event identity mismatch")
        if str(event.get("summary") or "") != payload.summary:
            raise ToolError("existing calendar event does not match frozen fields")
        start = _parse_provider_datetime((event.get("start") or {}).get("dateTime"))
        end = _parse_provider_datetime((event.get("end") or {}).get("dateTime"))
        if start is None or end is None:
            raise ToolError("existing calendar event does not match frozen fields")
        if start.astimezone(ZoneInfo("UTC")) != payload.start_at.astimezone(ZoneInfo("UTC")):
            raise ToolError("existing calendar event does not match frozen fields")
        if end.astimezone(ZoneInfo("UTC")) != payload.end_at.astimezone(ZoneInfo("UTC")):
            raise ToolError("existing calendar event does not match frozen fields")
        provider_description = event.get("description")
        if (payload.description or None) != (provider_description or None):
            raise ToolError("existing calendar event does not match frozen fields")
        provider_location = event.get("location")
        if (payload.location or None) != (provider_location or None):
            raise ToolError("existing calendar event does not match frozen fields")

    def _output(
        self,
        payload: CreateCalendarEventCanonicalInput,
        event: dict[str, Any],
        event_id: str,
        *,
        changed: bool,
    ) -> CreateCalendarEventOutput:
        html_link = event.get("htmlLink")
        canonical_uri = str(html_link) if isinstance(html_link, str) and html_link.strip() else None
        start = _parse_provider_datetime((event.get("start") or {}).get("dateTime")) or payload.start_at
        end = _parse_provider_datetime((event.get("end") or {}).get("dateTime")) or payload.end_at
        return CreateCalendarEventOutput(
            provider="google_calendar",
            account_email=payload.account_email,
            calendar_id=PRIMARY_CALENDAR_ID,
            event_id=event_id,
            summary=payload.summary,
            start_at=start,
            end_at=end,
            canonical_uri=canonical_uri,
            changed=changed,
        )

    def _bounded_provider_error(self, exc: GoogleApiError) -> str:
        message = (exc.message or "Google Calendar request failed").strip()
        lowered = message.lower()
        if any(token in lowered for token in ("access_token", "refresh_token", "bearer ", "ya29.")):
            return "Google Calendar request failed"
        return message[:500]
