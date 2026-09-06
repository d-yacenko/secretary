"""Bounded Gmail send_email execution after approval."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connectors.google.constants import GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.google.errors import GoogleApiError, GoogleConnectorError, GoogleOAuthError
from app.connectors.google.gmail_transport import GmailTransport, GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.core.config import settings
from app.db.models import ExternalActionAttempt, GoogleAccount
from app.db.session import SessionLocal
from app.tools.schemas import SendEmailCanonicalInput, SendEmailInput, SendEmailOutput, ToolError

ATTEMPT_STARTED = "started"
ATTEMPT_SUCCEEDED = "succeeded"
ATTEMPT_FAILED_DEFINITE = "failed_definite"
ATTEMPT_UNCERTAIN = "uncertain"

_RECONNECT_SEND_SCOPE_MESSAGE = (
    "Google must be reconnected to grant Gmail send permission"
)
_UNCERTAIN_DELIVERY_MESSAGE = (
    "could not confirm email delivery; not retrying send"
)
_MISMATCH_MESSAGE = "existing sent message does not match frozen fields"
_FAILED_DEFINITE_MESSAGE = "email send previously failed; create a new plan"


def generate_operation_id() -> str:
    return uuid4().hex


def rfc822_message_id_from_operation_id(operation_id: str) -> str:
    compact = operation_id.replace("-", "").lower()
    if len(compact) < 5 or len(compact) > 1024:
        raise ToolError("invalid operation_id")
    return f"<secretary.{compact}@secretary.invalid>"


def sent_message_query(rfc822_message_id: str) -> str:
    return f"in:sent rfc822msgid:{rfc822_message_id}"


def build_rfc822_raw(payload: SendEmailCanonicalInput) -> str:
    message = EmailMessage()
    message["From"] = payload.account_email
    message["To"] = ", ".join(payload.to)
    message["Subject"] = payload.subject
    message["Message-ID"] = payload.rfc822_message_id
    message.set_content(payload.body, subtype="plain", charset="utf-8")
    raw = message.as_bytes(policy=SMTP)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_body(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _header_from_list(headers: list[dict[str, Any]], name: str) -> str | None:
    for header in headers:
        if str(header.get("name") or "").lower() == name.lower():
            value = header.get("value")
            return str(value) if value is not None else None
    return None


def _parse_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    addresses: list[str] = []
    for part in value.split(","):
        _, addr = parseaddr(part.strip())
        if addr:
            addresses.append(addr)
    return addresses


def _extract_plain_body(payload: dict[str, Any]) -> str | None:
    mime_type = str(payload.get("mimeType") or "")
    body = payload.get("body") or {}
    data = body.get("data")
    if data and mime_type.startswith("text/plain"):
        padded = str(data) + "=" * (-len(str(data)) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            found = _extract_plain_body(part)
            if found is not None:
                return found
    return None


class EmailExternalActionService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        *,
        transport: GmailTransport | None = None,
        token_session_factory=SessionLocal,
        attempt_session_factory=SessionLocal,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._transport = transport or GmailTransport()
        self._token_session_factory = token_session_factory
        self._attempt_session_factory = attempt_session_factory

    def prepare_send_email(self, payload: SendEmailInput) -> SendEmailCanonicalInput:
        account = self._resolve_account(payload.account_email)
        self._require_send_scopes(account)
        operation_id = generate_operation_id()
        return SendEmailCanonicalInput(
            account_email=account.email,
            to=list(payload.to),
            subject=payload.subject,
            body=payload.body,
            operation_id=operation_id,
            rfc822_message_id=rfc822_message_id_from_operation_id(operation_id),
        )

    def send_email(self, payload: SendEmailCanonicalInput) -> SendEmailOutput:
        expected_id = rfc822_message_id_from_operation_id(payload.operation_id)
        if payload.rfc822_message_id != expected_id:
            raise ToolError("rfc822_message_id does not match operation_id")
        account = self._resolve_account(payload.account_email)
        self._require_send_scopes(account)
        attempt, claimed = self._claim_started(payload.operation_id)
        if not claimed:
            return self._resume_existing_attempt(account, payload, attempt)

        access_token = self._valid_access_token(account.id)
        raw = build_rfc822_raw(payload)
        try:
            sent = self._transport.send_message(
                access_token=access_token,
                user_id="me",
                raw=raw,
            )
        except GoogleApiError as exc:
            if _is_ambiguous_send_error(exc):
                return self._after_ambiguous_send(account, payload, access_token)
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_FAILED_DEFINITE,
                error=self._bounded_provider_error(exc),
            )
            raise ToolError(self._bounded_provider_error(exc)) from exc
        except httpx.RequestError:
            return self._after_ambiguous_send(account, payload, access_token)

        provider_id = str(sent.get("id") or "").strip() or None
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_SUCCEEDED,
            provider_external_id=provider_id,
            delivery_status="sent",
        )
        return self._output(payload, provider_id, delivery_status="sent", changed=True)

    def _resume_existing_attempt(
        self,
        account: GoogleAccount,
        payload: SendEmailCanonicalInput,
        attempt: ExternalActionAttempt,
    ) -> SendEmailOutput:
        if attempt.state == ATTEMPT_SUCCEEDED:
            return self._output(
                payload,
                attempt.provider_external_id,
                delivery_status="already_sent",
                changed=False,
            )
        if attempt.state == ATTEMPT_FAILED_DEFINITE:
            raise ToolError(_FAILED_DEFINITE_MESSAGE)
        access_token = self._valid_access_token(account.id)
        return self._reconcile_sent(account, payload, access_token)

    def _after_ambiguous_send(
        self,
        account: GoogleAccount,
        payload: SendEmailCanonicalInput,
        access_token: str,
    ) -> SendEmailOutput:
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_UNCERTAIN,
            error=_UNCERTAIN_DELIVERY_MESSAGE,
        )
        return self._reconcile_sent(account, payload, access_token)

    def _reconcile_sent(
        self,
        account: GoogleAccount,
        payload: SendEmailCanonicalInput,
        access_token: str,
    ) -> SendEmailOutput:
        try:
            ids = self._transport.list_message_ids(
                access_token=access_token,
                user_id="me",
                query=sent_message_query(payload.rfc822_message_id),
                max_results=5,
            )
        except (GoogleApiError, httpx.RequestError) as exc:
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_UNCERTAIN,
                error=_UNCERTAIN_DELIVERY_MESSAGE,
            )
            raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE) from exc

        if not ids:
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_UNCERTAIN,
                error=_UNCERTAIN_DELIVERY_MESSAGE,
            )
            raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE)

        matched: dict[str, Any] | None = None
        for message_id in ids:
            try:
                message = self._transport.get_message(access_token, "me", message_id)
            except (GoogleApiError, httpx.RequestError) as exc:
                self._persist_attempt_state(
                    payload.operation_id,
                    ATTEMPT_UNCERTAIN,
                    error=_UNCERTAIN_DELIVERY_MESSAGE,
                )
                raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE) from exc
            if not isinstance(message, dict):
                raise ToolError(_MISMATCH_MESSAGE)
            if self._message_identity_matches(payload, message):
                if not self._message_content_matches(account, payload, message):
                    raise ToolError(_MISMATCH_MESSAGE)
                matched = message
                continue
            if self._header_value(message, "Message-ID") == payload.rfc822_message_id:
                raise ToolError(_MISMATCH_MESSAGE)
        if matched is None:
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_UNCERTAIN,
                error=_UNCERTAIN_DELIVERY_MESSAGE,
            )
            raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE)

        provider_id = str(matched.get("id") or "").strip() or None
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_SUCCEEDED,
            provider_external_id=provider_id,
            delivery_status="already_sent",
        )
        return self._output(
            payload,
            provider_id,
            delivery_status="already_sent",
            changed=False,
        )

    def _claim_started(self, operation_id: str) -> tuple[ExternalActionAttempt, bool]:
        session = self._attempt_session_factory()
        try:
            attempt = ExternalActionAttempt(
                user_id=self._user_id,
                operation_id=operation_id,
                tool_name="send_email",
                state=ATTEMPT_STARTED,
                started_at=_utcnow(),
            )
            session.add(attempt)
            session.commit()
            session.refresh(attempt)
            return attempt, True
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(ExternalActionAttempt).where(
                    ExternalActionAttempt.user_id == self._user_id,
                    ExternalActionAttempt.operation_id == operation_id,
                )
            )
            if existing is None:
                raise ToolError("failed to claim send_email operation")
            return existing, False
        finally:
            session.close()

    def _persist_attempt_state(
        self,
        operation_id: str,
        state: str,
        *,
        provider_external_id: str | None = None,
        delivery_status: str | None = None,
        error: str | None = None,
    ) -> None:
        session = self._attempt_session_factory()
        try:
            attempt = session.scalar(
                select(ExternalActionAttempt).where(
                    ExternalActionAttempt.user_id == self._user_id,
                    ExternalActionAttempt.operation_id == operation_id,
                )
            )
            if attempt is None:
                return
            if attempt.state == ATTEMPT_SUCCEEDED:
                return
            if attempt.state == ATTEMPT_FAILED_DEFINITE and state != ATTEMPT_FAILED_DEFINITE:
                return
            metadata = dict(attempt.result_metadata or {})
            if delivery_status:
                metadata["delivery_status"] = delivery_status
            if error:
                metadata["error"] = error[:500]
            attempt.state = state
            attempt.result_metadata = metadata
            if provider_external_id:
                attempt.provider_external_id = provider_external_id[:200]
            if state != ATTEMPT_STARTED:
                attempt.finished_at = _utcnow()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
            token = token_manager.get_valid_access_token(account_id, self._user_id)
            token_session.commit()
            return token
        except (GoogleConnectorError, GoogleOAuthError) as exc:
            token_session.rollback()
            raise ToolError(exc.message) from exc
        except Exception:
            token_session.rollback()
            raise
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

    def _require_send_scopes(self, account: GoogleAccount) -> None:
        scopes = {str(scope) for scope in (account.scopes or [])}
        if GMAIL_SEND_SCOPE not in scopes or GMAIL_READONLY_SCOPE not in scopes:
            raise ToolError(_RECONNECT_SEND_SCOPE_MESSAGE)

    def _account_store(self) -> GoogleAccountStore:
        if not settings.secretary_credential_key:
            raise ToolError("google credentials are not configured")
        encryption = CredentialEncryption(settings.secretary_credential_key)
        return GoogleAccountStore(self._session, encryption)

    def _message_identity_matches(
        self,
        payload: SendEmailCanonicalInput,
        message: dict[str, Any],
    ) -> bool:
        return self._header_value(message, "Message-ID") == payload.rfc822_message_id

    def _message_content_matches(
        self,
        account: GoogleAccount,
        payload: SendEmailCanonicalInput,
        message: dict[str, Any],
    ) -> bool:
        from_addresses = [
            addr.lower() for addr in _parse_addresses(self._header_value(message, "From") or "")
        ]
        if account.email.lower() not in from_addresses:
            return False
        to_addresses = {
            addr.lower() for addr in _parse_addresses(self._header_value(message, "To") or "")
        }
        expected_to = {addr.lower() for addr in payload.to}
        if to_addresses != expected_to:
            return False
        if (self._header_value(message, "Subject") or "") != payload.subject:
            return False
        payload_body = message.get("payload") if isinstance(message.get("payload"), dict) else message
        if not isinstance(payload_body, dict):
            return False
        plain = _extract_plain_body(payload_body)
        if plain is None:
            return False
        return _normalize_body(plain) == _normalize_body(payload.body)

    def _header_value(self, message: dict[str, Any], name: str) -> str | None:
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else message
        headers = payload.get("headers") if isinstance(payload, dict) else None
        if not isinstance(headers, list):
            return None
        return _header_from_list(headers, name)

    def _output(
        self,
        payload: SendEmailCanonicalInput,
        provider_message_id: str | None,
        *,
        delivery_status: str,
        changed: bool,
    ) -> SendEmailOutput:
        return SendEmailOutput(
            provider="gmail",
            account_email=payload.account_email,
            to=list(payload.to),
            subject=payload.subject,
            provider_message_id=provider_message_id,
            delivery_status=delivery_status,  # type: ignore[arg-type]
            changed=changed,
        )

    def _bounded_provider_error(self, exc: GoogleApiError) -> str:
        message = (exc.message or "Gmail request failed").strip()
        lowered = message.lower()
        if any(token in lowered for token in ("access_token", "refresh_token", "bearer ", "ya29.")):
            return "Gmail request failed"
        return message[:500]


def _is_ambiguous_send_error(exc: GoogleApiError) -> bool:
    if exc.retryable:
        return True
    return exc.status_code is not None and exc.status_code >= 500
