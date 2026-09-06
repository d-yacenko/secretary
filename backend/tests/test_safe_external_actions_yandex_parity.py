"""Yandex parity for universal send_email and create_calendar_event."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from email.policy import SMTP
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete

from app.connectors.google.constants import (
    CALENDAR_EVENTS_SCOPE,
    CALENDAR_READONLY_SCOPE,
    DRIVE_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.caldav_transport import CalDavCalendar, FakeCalDavTransport
from app.connectors.yandex.caldav_write import (
    event_href_from_operation_id,
    select_default_yandex_calendar,
)
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.connectors.yandex.errors import YandexCalDavError, YandexSmtpError
from app.connectors.yandex.imap_mailboxes import (
    ImapMailbox,
    parse_imap_list_line,
    sent_folder_from_mailboxes,
)
from app.connectors.yandex.imap_transport import FakeImapTransport, parse_imap_internaldate
from app.connectors.yandex.smtp_transport import FakeSmtpTransport
from app.core.config import settings
from app.db.models import ExternalActionAttempt, GoogleAccount, PendingActionPlan, User
from app.db.session import SessionLocal
from app.services.action_plan_service import ActionPlanService
from app.services.calendar_external_action_service import CalendarExternalActionService
from app.services.domain_tool_service import DomainToolService
from app.services.email_external_action_service import (
    ATTEMPT_STARTED,
    SECRETARY_OPERATION_HEADER,
    EmailExternalActionService,
    build_email_message,
    rfc822_message_id_from_operation_id,
    yandex_sent_coarse_imap_bounds,
    yandex_sent_evidence_window,
)
from app.tools.execution_context import ExecutionContext
from app.tools.gateway import ToolExecutionGateway
from app.tools.results import ToolExecutionStatus
from app.tools.schemas import (
    CreateCalendarEventCanonicalInput,
    SendEmailCanonicalInput,
    SendEmailInput,
    ToolError,
)


class FakeCalendarTransport:
    def __init__(self) -> None:
        self.insert_calls: list[dict] = []
        self.events: dict[str, dict] = {}

    def insert_event(self, access_token: str, calendar_id: str, body: dict) -> dict:
        self.insert_calls.append({"calendar_id": calendar_id, "body": dict(body)})
        event_id = str(body["id"])
        stored = {
            "id": event_id,
            "summary": body["summary"],
            "start": dict(body["start"]),
            "end": dict(body["end"]),
        }
        self.events[event_id] = stored
        return dict(stored)

    def get_event(self, access_token: str, calendar_id: str, event_id: str) -> dict:
        return dict(self.events[event_id])


class FakeGmailTransport:
    def __init__(self) -> None:
        self.send_calls: list[dict] = []

    def send_message(self, access_token: str, user_id: str, raw: str) -> dict:
        self.send_calls.append({"raw": raw})
        return {"id": f"gmail-{len(self.send_calls)}"}


SENT_FOLDER = "Отправленные"
CALENDAR_HREF = "/calendars/user@yandex.ru/events-default/"


@pytest.fixture
def credential_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def google_settings(monkeypatch: pytest.MonkeyPatch, tmp_path, credential_key: str) -> None:
    client_file = tmp_path / "google-oauth-client.json"
    client_file.write_text(
        '{"web": {"client_id": "test-client-id", "client_secret": "test-client-secret"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "secretary_credential_key", credential_key)
    monkeypatch.setattr(settings, "google_oauth_client_file", str(client_file))
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost/auth/google/callback")


@pytest.fixture
def owner(db_session):
    user_id = uuid4()
    db_session.add(User(id=user_id, display_name="parity-user"))
    db_session.flush()
    return user_id


def _send_scopes() -> list[str]:
    return [
        GMAIL_READONLY_SCOPE,
        GMAIL_SEND_SCOPE,
        CALENDAR_READONLY_SCOPE,
        CALENDAR_EVENTS_SCOPE,
        DRIVE_READONLY_SCOPE,
    ]


def _add_google(db_session, credential_key: str, email: str, *, user_id):
    return GoogleAccountStore(db_session, CredentialEncryption(credential_key)).upsert_tokens(
        user_id=user_id,
        email=email,
        scopes=_send_scopes(),
        access_token="access-token",
        refresh_token="refresh-token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
    )


def _add_yandex_mail(db_session, credential_key: str, email: str, *, user_id):
    return YandexMailAccountStore(db_session, CredentialEncryption(credential_key)).upsert_account(
        user_id=user_id,
        email=email,
        app_password="yandex-app-password",
        imap_host="imap.yandex.ru",
        imap_port=993,
    )


def _add_yandex_calendar(db_session, credential_key: str, email: str, *, user_id):
    return YandexCalendarAccountStore(db_session, CredentialEncryption(credential_key)).upsert_account(
        user_id=user_id,
        email=email,
        app_password="yandex-caldav-password",
        caldav_host="caldav.yandex.ru",
    )


def _mail_args(**overrides) -> dict:
    payload = {
        "to": ["ivan@example.com"],
        "subject": "Статус задачи",
        "body": "Краткий статус: работа продолжается.",
    }
    payload.update(overrides)
    return payload


def _event_args(**overrides) -> dict:
    payload = {
        "summary": "Созвон",
        "start_at": datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        "end_at": datetime(2026, 9, 6, 12, 30, tzinfo=UTC),
        "description": "Weekly",
        "location": "Office",
    }
    payload.update(overrides)
    return payload


def _sent_imap() -> FakeImapTransport:
    return FakeImapTransport(
        folder="INBOX",
        messages={},
        mailboxes=[
            ImapMailbox(flags=frozenset({"HASNOCHILDREN"}), name="INBOX"),
            ImapMailbox(flags=frozenset({"HASNOCHILDREN", "SENT"}), name=SENT_FOLDER),
        ],
        folder_messages={"INBOX": {}, SENT_FOLDER: {}},
    )


def _mail_fakes() -> tuple[FakeSmtpTransport, FakeImapTransport]:
    imap = _sent_imap()
    return FakeSmtpTransport(imap=imap, sent_folder=SENT_FOLDER), imap


def _calendar_fake() -> FakeCalDavTransport:
    return FakeCalDavTransport(
        calendars=[CalDavCalendar(href=CALENDAR_HREF, display_name="default", sync_token="t")]
    )


def _patch_mail(monkeypatch, smtp: FakeSmtpTransport, imap: FakeImapTransport) -> None:
    original_init = DomainToolService.__init__

    def patched(self, *args, **kwargs):
        kwargs.setdefault("yandex_smtp_transport", smtp)
        kwargs.setdefault("yandex_imap_transport", imap)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(DomainToolService, "__init__", patched)


def _patch_calendar(monkeypatch, caldav: FakeCalDavTransport) -> None:
    original_init = DomainToolService.__init__

    def patched(self, *args, **kwargs):
        kwargs.setdefault("yandex_caldav_transport", caldav)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(DomainToolService, "__init__", patched)


def _keepalive(session):
    class _Proxy:
        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def close(self) -> None:
            return None

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __setattr__(self, name, value):
            setattr(self._inner, name, value)

    return _Proxy(session)


def _tools_mail(db_session, user_id, smtp, imap, gmail=None):
    return DomainToolService(
        db_session,
        user_id,
        gmail_transport=gmail or FakeGmailTransport(),
        yandex_smtp_transport=smtp,
        yandex_imap_transport=imap,
        attempt_session_factory=lambda: _keepalive(db_session),
    )


def _tools_cal(db_session, user_id, caldav, google=None):
    return DomainToolService(
        db_session,
        user_id,
        calendar_transport=google or FakeCalendarTransport(),
        yandex_caldav_transport=caldav,
    )


def test_imap_sent_folder_uses_special_use_not_english_name() -> None:
    parsed = parse_imap_list_line('(\\HasNoChildren \\Sent) "/" "Отправленные"')
    assert parsed is not None
    assert sent_folder_from_mailboxes([parsed]) == "Отправленные"
    with pytest.raises(Exception, match="Sent folder"):
        sent_folder_from_mailboxes([ImapMailbox(flags=frozenset(), name="Sent")])


def test_provider_resolution_matrix(db_session, google_settings, credential_key, owner):
    gateway = ToolExecutionGateway()
    smtp, imap = _mail_fakes()
    tools = _tools_mail(db_session, owner, smtp, imap)
    none = gateway.execute(tools, "send_email", _mail_args(), context=ExecutionContext.INTERACTIVE_ASSISTANT)
    assert none.status == ToolExecutionStatus.TOOL_ERROR
    assert "connected" in (none.error or "").lower()

    _add_google(db_session, credential_key, "only-google@example.com", user_id=owner)
    google_only = gateway.execute(tools, "send_email", _mail_args(), context=ExecutionContext.INTERACTIVE_ASSISTANT)
    assert google_only.staged_action["arguments"]["provider"] == "google"

    db_session.execute(delete(GoogleAccount).where(GoogleAccount.user_id == owner))
    db_session.flush()
    _add_yandex_mail(db_session, credential_key, "only-yandex@yandex.ru", user_id=owner)
    yandex_only = gateway.execute(tools, "send_email", _mail_args(), context=ExecutionContext.INTERACTIVE_ASSISTANT)
    assert yandex_only.staged_action["arguments"]["provider"] == "yandex"

    _add_google(db_session, credential_key, "google@example.com", user_id=owner)
    both = gateway.execute(tools, "send_email", _mail_args(), context=ExecutionContext.INTERACTIVE_ASSISTANT)
    assert both.status == ToolExecutionStatus.TOOL_ERROR

    assert gateway.execute(
        tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    ).staged_action["arguments"]["provider"] == "yandex"
    assert gateway.execute(
        tools, "send_email", _mail_args(provider="google"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    ).staged_action["arguments"]["provider"] == "google"
    assert gateway.execute(
        tools,
        "send_email",
        _mail_args(account_email="only-yandex@yandex.ru"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    ).staged_action["arguments"]["provider"] == "yandex"

    _add_yandex_mail(db_session, credential_key, "google@example.com", user_id=owner)
    clash = gateway.execute(
        tools, "send_email", _mail_args(account_email="google@example.com"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    assert clash.status == ToolExecutionStatus.TOOL_ERROR

    other = uuid4()
    db_session.add(User(id=other, display_name="other"))
    db_session.flush()
    _add_google(db_session, credential_key, "foreign@example.com", user_id=other)
    foreign = gateway.execute(
        tools, "send_email", _mail_args(account_email="foreign@example.com"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    assert foreign.status == ToolExecutionStatus.TOOL_ERROR
    assert smtp.send_calls == []


def test_legacy_google_plan_without_provider(db_session, google_settings, credential_key, owner, monkeypatch):
    gmail = FakeGmailTransport()
    smtp, imap = _mail_fakes()
    monkeypatch.setattr(
        EmailExternalActionService, "_valid_access_token", lambda self, account_id: "access-token"
    )
    _add_google(db_session, credential_key, "user@example.com", user_id=owner)
    operation_id = "deadbeefdeadbeefdeadbeefdeadbeef"
    args = {
        "account_email": "user@example.com",
        "to": ["ivan@example.com"],
        "subject": "Legacy",
        "body": "Legacy body",
        "operation_id": operation_id,
        "rfc822_message_id": rfc822_message_id_from_operation_id(operation_id),
    }
    tools = _tools_mail(db_session, owner, smtp, imap, gmail=gmail)
    result = ToolExecutionGateway().execute(
        tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    assert result.success is True
    assert len(gmail.send_calls) == 1
    assert smtp.send_calls == []
    _add_yandex_mail(db_session, credential_key, "user@example.com", user_id=owner)
    blocked = ToolExecutionGateway().execute(
        tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    assert blocked.success is False
    assert len(gmail.send_calls) == 1


def test_yandex_mail_approval_gates(db_session, google_settings, credential_key, owner, monkeypatch):
    smtp, imap = _mail_fakes()
    _patch_mail(monkeypatch, smtp, imap)
    _add_yandex_mail(db_session, credential_key, "user@yandex.ru", user_id=owner)
    tools = _tools_mail(db_session, owner, smtp, imap)
    gateway = ToolExecutionGateway()
    interactive = gateway.execute(
        tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    assert interactive.status == ToolExecutionStatus.APPROVAL_REQUIRED
    assert interactive.staged_action["arguments"]["provider"] == "yandex"
    assert smtp.send_calls == []
    mcp = gateway.execute(tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.MCP)
    assert mcp.status == ToolExecutionStatus.APPROVAL_REQUIRED
    service = ActionPlanService(db_session, owner)
    rejected = gateway.execute(
        tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    service.reject(service.create_plan([rejected.staged_action]).id)
    expired = gateway.execute(
        tools,
        "send_email",
        _mail_args(provider="yandex", subject="Expire"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    expired_plan = service.create_plan([expired.staged_action])
    row = db_session.get(PendingActionPlan, expired_plan.id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    service.approve(expired_plan.id)
    assert smtp.send_calls == []


def test_yandex_mail_approve_sends_once(google_settings, credential_key, monkeypatch):
    smtp, imap = _mail_fakes()
    _patch_mail(monkeypatch, smtp, imap)
    session = SessionLocal()
    user_id = uuid4()
    try:
        session.add(User(id=user_id, display_name="yandex-mail"))
        session.commit()
        _add_yandex_mail(session, credential_key, "user@yandex.ru", user_id=user_id)
        session.commit()
        tools = _tools_mail(session, user_id, smtp, imap)
        staged = ToolExecutionGateway().execute(
            tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
        )
        assert "yandex-app-password" not in str(staged.staged_action)
        plan = ActionPlanService(session, user_id).create_plan([staged.staged_action])
        assert "operation_id" not in str(plan.actions)
        first = ActionPlanService(session, user_id).approve(plan.id)
        assert first.result["actions"][0]["output"]["changed"] is True
        assert first.result["actions"][0]["output"]["provider"] == "yandex"
        assert len(smtp.send_calls) == 1
        assert SECRETARY_OPERATION_HEADER.encode() in smtp.send_calls[0]["message_bytes"]
        assert b"yandex-app-password" not in smtp.send_calls[0]["message_bytes"]
        ActionPlanService(session, user_id).approve(plan.id)
        assert len(smtp.send_calls) == 1
        repeated = ToolExecutionGateway().execute(
            tools,
            "send_email",
            staged.staged_action["arguments"],
            context=ExecutionContext.APPROVED_ACTION_PLAN,
        )
        assert repeated.success is True
        assert repeated.output["changed"] is False
        assert len(smtp.send_calls) == 1
    finally:
        session.execute(delete(ExternalActionAttempt).where(ExternalActionAttempt.user_id == user_id))
        session.execute(delete(PendingActionPlan).where(PendingActionPlan.user_id == user_id))
        session.commit()
        session.close()


def test_yandex_mail_concurrent_crash_reconcile(google_settings, credential_key, monkeypatch):
    smtp, imap = _mail_fakes()
    _patch_mail(monkeypatch, smtp, imap)
    session = SessionLocal()
    user_id = uuid4()
    try:
        session.add(User(id=user_id, display_name="yandex-conc"))
        session.commit()
        _add_yandex_mail(session, credential_key, "user@yandex.ru", user_id=user_id)
        session.commit()
        args = ToolExecutionGateway().execute(
            _tools_mail(session, user_id, smtp, imap),
            "send_email",
            _mail_args(provider="yandex"),
            context=ExecutionContext.INTERACTIVE_ASSISTANT,
        ).staged_action["arguments"]

        def worker() -> None:
            worker_session = SessionLocal()
            try:
                ToolExecutionGateway().execute(
                    _tools_mail(worker_session, user_id, smtp, imap),
                    "send_email",
                    args,
                    context=ExecutionContext.APPROVED_ACTION_PLAN,
                )
            finally:
                worker_session.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(smtp.send_calls) == 1

        smtp2, imap2 = _mail_fakes()
        _patch_mail(monkeypatch, smtp2, imap2)
        args2 = ToolExecutionGateway().execute(
            _tools_mail(session, user_id, smtp2, imap2),
            "send_email",
            _mail_args(provider="yandex", subject="Crash"),
            context=ExecutionContext.INTERACTIVE_ASSISTANT,
        ).staged_action["arguments"]
        imap2.add_message(
            SENT_FOLDER,
            7,
            build_email_message(SendEmailCanonicalInput.model_validate(args2)).as_bytes(policy=SMTP),
        )
        crash = SessionLocal()
        crash.add(
            ExternalActionAttempt(
                user_id=user_id,
                operation_id=args2["operation_id"],
                tool_name="send_email",
                state=ATTEMPT_STARTED,
                started_at=datetime.now(UTC),
            )
        )
        crash.commit()
        crash.close()
        resumed = ToolExecutionGateway().execute(
            _tools_mail(session, user_id, smtp2, imap2),
            "send_email",
            args2,
            context=ExecutionContext.APPROVED_ACTION_PLAN,
        )
        assert resumed.success is True
        assert resumed.output["changed"] is False
        assert smtp2.send_calls == []
    finally:
        session.execute(delete(ExternalActionAttempt).where(ExternalActionAttempt.user_id == user_id))
        session.execute(delete(PendingActionPlan).where(PendingActionPlan.user_id == user_id))
        session.commit()
        session.close()


def _execute_yandex_send(db_session, owner, smtp, imap):
    tools = _tools_mail(db_session, owner, smtp, imap)
    gateway = ToolExecutionGateway()
    staged = gateway.execute(
        tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    result = gateway.execute(
        tools, "send_email", staged.staged_action["arguments"], context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    return result, smtp, imap


def test_yandex_mail_reconciliation_cases(db_session, google_settings, credential_key, owner, monkeypatch):
    _add_yandex_mail(db_session, credential_key, "user@yandex.ru", user_id=owner)

    smtp, imap = _mail_fakes()
    smtp.lose_send_response = True
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is True
    assert result.output["changed"] is False
    assert len(smtp.send_calls) == 1

    smtp, imap = _mail_fakes()
    smtp.send_error = YandexSmtpError("try later", retryable=True)
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is True

    smtp, imap = _mail_fakes()
    smtp.persist_on_send = False
    smtp.lose_send_response = True
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is False

    smtp, imap = _mail_fakes()
    smtp.strip_operation_header = True
    smtp.lose_send_response = True
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is False

    smtp, imap = _mail_fakes()
    smtp.field_overrides = {"Subject": "other"}
    smtp.lose_send_response = True
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is False
    assert "does not match" in (result.error or "")

    smtp, imap = _mail_fakes()
    smtp.also_store_tagged_clone = True
    smtp.lose_send_response = True
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is False
    assert "multiple" in (result.error or "")

    smtp, imap = _mail_fakes()
    imap._folder_messages[SENT_FOLDER] = {
        index: b"From: a@b.c\r\nSubject: x\r\n\r\nx" for index in range(1, 220)
    }
    smtp.persist_on_send = False
    smtp.lose_send_response = True
    result, smtp, imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert result.success is False
    assert imap.window_search_calls[0]["folder"] == SENT_FOLDER
    assert imap.window_search_calls[0]["max_results"] == 200
    assert imap.fetch_calls == []
    assert imap.internaldate_fetch_calls == []
    assert len(smtp.send_calls) == 1

    smtp, imap = _mail_fakes()
    smtp.send_error = YandexSmtpError("password=yandex-app-password leaked", retryable=False)
    result, smtp, _imap = _execute_yandex_send(db_session, owner, smtp, imap)
    assert "password" not in (result.error or "").lower()
    assert "yandex-app-password" not in (result.error or "")


def test_cross_provider_mail_dispatch(db_session, google_settings, credential_key, owner, monkeypatch):
    gmail = FakeGmailTransport()
    smtp, imap = _mail_fakes()
    monkeypatch.setattr(
        EmailExternalActionService, "_valid_access_token", lambda self, account_id: "access-token"
    )
    _add_google(db_session, credential_key, "user@example.com", user_id=owner)
    _add_yandex_mail(db_session, credential_key, "user@yandex.ru", user_id=owner)
    tools = DomainToolService(
        db_session,
        owner,
        gmail_transport=gmail,
        yandex_smtp_transport=smtp,
        yandex_imap_transport=imap,
        attempt_session_factory=lambda: _keepalive(db_session),
    )
    gateway = ToolExecutionGateway()
    google_staged = gateway.execute(
        tools, "send_email", _mail_args(provider="google"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    gateway.execute(
        tools,
        "send_email",
        google_staged.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert len(gmail.send_calls) == 1
    assert smtp.send_calls == []
    yandex_staged = gateway.execute(
        tools, "send_email", _mail_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    gateway.execute(
        tools,
        "send_email",
        yandex_staged.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert len(gmail.send_calls) == 1
    assert len(smtp.send_calls) == 1


def test_yandex_calendar_create_and_gates(db_session, google_settings, credential_key, owner, monkeypatch):
    caldav = _calendar_fake()
    google = FakeCalendarTransport()
    _patch_calendar(monkeypatch, caldav)
    _add_yandex_calendar(db_session, credential_key, "user@yandex.ru", user_id=owner)
    tools = _tools_cal(db_session, owner, caldav, google)
    gateway = ToolExecutionGateway()
    interactive = gateway.execute(
        tools,
        "create_calendar_event",
        _event_args(provider="yandex"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    assert interactive.status == ToolExecutionStatus.APPROVAL_REQUIRED
    args = interactive.staged_action["arguments"]
    assert args["provider"] == "yandex"
    assert args["calendar_href"] == CALENDAR_HREF
    assert caldav.put_calls == []
    public = ActionPlanService(db_session, owner).create_plan([interactive.staged_action])
    assert "calendar_href" not in str(public.actions)
    assert "yandex-caldav-password" not in str(public.actions)
    mcp = gateway.execute(
        tools, "create_calendar_event", _event_args(provider="yandex"), context=ExecutionContext.MCP
    )
    assert mcp.status == ToolExecutionStatus.APPROVAL_REQUIRED
    service = ActionPlanService(db_session, owner)
    rejected = gateway.execute(
        tools,
        "create_calendar_event",
        _event_args(provider="yandex", summary="Reject"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    service.reject(service.create_plan([rejected.staged_action]).id)
    expired = gateway.execute(
        tools,
        "create_calendar_event",
        _event_args(provider="yandex", summary="Expire"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    expired_plan = service.create_plan([expired.staged_action])
    row = db_session.get(PendingActionPlan, expired_plan.id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    service.approve(expired_plan.id)
    assert caldav.put_calls == []
    executed = gateway.execute(
        tools, "create_calendar_event", args, context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    assert executed.success is True
    assert executed.output["provider"] == "yandex_calendar"
    assert len(caldav.put_calls) == 1
    assert google.insert_calls == []
    href = event_href_from_operation_id(CALENDAR_HREF, args["operation_id"])
    assert caldav.put_calls[0]["href"] == href
    repeated = gateway.execute(
        tools, "create_calendar_event", args, context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    assert repeated.output["changed"] is False
    assert caldav.put_hrefs == [href, href]


def test_yandex_calendar_mismatch_timeout_rejects(
    db_session, google_settings, credential_key, owner, monkeypatch
):
    caldav = _calendar_fake()
    _patch_calendar(monkeypatch, caldav)
    _add_yandex_calendar(db_session, credential_key, "user@yandex.ru", user_id=owner)
    tools = _tools_cal(db_session, owner, caldav)
    gateway = ToolExecutionGateway()
    staged = gateway.execute(
        tools,
        "create_calendar_event",
        _event_args(provider="yandex"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    args = staged.staged_action["arguments"]
    href = event_href_from_operation_id(CALENDAR_HREF, args["operation_id"])
    caldav.objects[href] = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:other\nSUMMARY:nope\nEND:VEVENT\nEND:VCALENDAR\n"
    mismatch = gateway.execute(
        tools, "create_calendar_event", args, context=ExecutionContext.APPROVED_ACTION_PLAN
    )
    assert mismatch.success is False

    caldav2 = _calendar_fake()
    caldav2.lose_put_response = True
    _patch_calendar(monkeypatch, caldav2)
    tools2 = _tools_cal(db_session, owner, caldav2)
    staged2 = gateway.execute(
        tools2,
        "create_calendar_event",
        _event_args(provider="yandex", summary="Timeout"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    timeout = gateway.execute(
        tools2,
        "create_calendar_event",
        staged2.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert timeout.success is True
    href2 = event_href_from_operation_id(CALENDAR_HREF, staged2.staged_action["arguments"]["operation_id"])
    assert caldav2.put_hrefs == [href2]

    caldav3 = _calendar_fake()
    caldav3.put_error = YandexCalDavError("HTTP 503", operation="PUT", status_code=503, retryable=True)
    _patch_calendar(monkeypatch, caldav3)
    tools3 = _tools_cal(db_session, owner, caldav3)
    staged3 = gateway.execute(
        tools3,
        "create_calendar_event",
        _event_args(provider="yandex", summary="Retryable"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    retryable = gateway.execute(
        tools3,
        "create_calendar_event",
        staged3.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert retryable.success is True

    for extra in (
        {"attendees": ["a@b.c"]},
        {"ics": "BEGIN:VCALENDAR"},
        {"calendar_href": "/calendars/other/"},
        {"rrule": "FREQ=DAILY"},
    ):
        rejected = gateway.execute(
            tools,
            "create_calendar_event",
            _event_args(provider="yandex", **extra),
            context=ExecutionContext.INTERACTIVE_ASSISTANT,
        )
        assert rejected.status == ToolExecutionStatus.TOOL_ERROR


def test_yandex_calendar_default_and_cross_provider(
    db_session, google_settings, credential_key, owner, monkeypatch
):
    many = FakeCalDavTransport(
        calendars=[
            CalDavCalendar(href="/calendars/user@yandex.ru/work/", display_name="Work", sync_token=None),
            CalDavCalendar(href="/calendars/user@yandex.ru/home/", display_name="Home", sync_token=None),
        ]
    )
    _patch_calendar(monkeypatch, many)
    _add_yandex_calendar(db_session, credential_key, "user@yandex.ru", user_id=owner)
    blocked = ToolExecutionGateway().execute(
        _tools_cal(db_session, owner, many),
        "create_calendar_event",
        _event_args(provider="yandex"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    assert blocked.status == ToolExecutionStatus.TOOL_ERROR
    assert many.put_calls == []

    google = FakeCalendarTransport()
    yandex = _calendar_fake()
    monkeypatch.setattr(
        CalendarExternalActionService, "_valid_access_token", lambda self, account_id: "access-token"
    )
    _add_google(db_session, credential_key, "user@example.com", user_id=owner)
    tools = DomainToolService(
        db_session, owner, calendar_transport=google, yandex_caldav_transport=yandex
    )
    gateway = ToolExecutionGateway()
    g_staged = gateway.execute(
        tools, "create_calendar_event", _event_args(provider="google"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    gateway.execute(
        tools,
        "create_calendar_event",
        g_staged.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert len(google.insert_calls) == 1
    assert yandex.put_calls == []
    y_staged = gateway.execute(
        tools, "create_calendar_event", _event_args(provider="yandex"), context=ExecutionContext.INTERACTIVE_ASSISTANT
    )
    gateway.execute(
        tools,
        "create_calendar_event",
        y_staged.staged_action["arguments"],
        context=ExecutionContext.APPROVED_ACTION_PLAN,
    )
    assert len(google.insert_calls) == 1
    assert len(yandex.put_calls) == 1


def test_select_default_yandex_calendar_requires_events_default() -> None:
    default = CalDavCalendar(
        href="/calendars/user@yandex.ru/events-default/",
        display_name="Shared looking name",
        sync_token="t",
    )
    work = CalDavCalendar(href="/calendars/user@yandex.ru/work/", display_name="Work", sync_token=None)
    home = CalDavCalendar(href="/calendars/user@yandex.ru/home/", display_name="Home", sync_token=None)
    other_default = CalDavCalendar(
        href="/calendars/other@yandex.ru/events-default/",
        display_name="Other",
        sync_token=None,
    )
    assert select_default_yandex_calendar([default]) is default
    assert select_default_yandex_calendar([work, default, home]) is default
    with pytest.raises(ToolError, match="not available"):
        select_default_yandex_calendar([])
    with pytest.raises(ToolError, match="cannot identify default"):
        select_default_yandex_calendar([work])
    with pytest.raises(ToolError, match="cannot identify default"):
        select_default_yandex_calendar([work, home])
    with pytest.raises(ToolError, match="cannot identify default"):
        select_default_yandex_calendar([default, other_default])


def test_yandex_calendar_sole_non_default_fails_closed(
    db_session, google_settings, credential_key, owner, monkeypatch
):
    sole = FakeCalDavTransport(
        calendars=[
            CalDavCalendar(href="/calendars/user@yandex.ru/shared/", display_name="Shared", sync_token="t")
        ]
    )
    _patch_calendar(monkeypatch, sole)
    _add_yandex_calendar(db_session, credential_key, "user@yandex.ru", user_id=owner)
    blocked = ToolExecutionGateway().execute(
        _tools_cal(db_session, owner, sole),
        "create_calendar_event",
        _event_args(provider="yandex"),
        context=ExecutionContext.INTERACTIVE_ASSISTANT,
    )
    assert blocked.status == ToolExecutionStatus.TOOL_ERROR
    assert "default" in (blocked.error or "").lower()
    assert sole.put_calls == []


def test_parse_imap_internaldate_uses_server_timestamp() -> None:
    parsed = parse_imap_internaldate(b'1 (UID 7 INTERNALDATE "06-Sep-2026 10:00:00 +0000")')
    assert parsed == datetime(2026, 9, 6, 10, 0, tzinfo=UTC)


def _tagged_sent_bytes(args: dict, *, subject: str | None = None, date_header: str | None = None) -> bytes:
    message = build_email_message(SendEmailCanonicalInput.model_validate(args))
    if subject is not None:
        message.replace_header("Subject", subject)
    if date_header is not None:
        if "Date" in message:
            message.replace_header("Date", date_header)
        else:
            message["Date"] = date_header
    return message.as_bytes(policy=SMTP)


def test_yandex_sent_internaldate_window(google_settings, credential_key):
    started_at = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
    window_start, window_end = yandex_sent_evidence_window(started_at)
    assert window_start == datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    assert window_end == datetime(2026, 9, 6, 14, 0, tzinfo=UTC)
    since, before = yandex_sent_coarse_imap_bounds(started_at)
    assert since == datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    assert before == datetime(2026, 9, 7, 0, 0, tzinfo=UTC)

    session = SessionLocal()
    user_id = uuid4()
    try:
        session.add(User(id=user_id, display_name="yandex-window"))
        session.commit()
        _add_yandex_mail(session, credential_key, "user@yandex.ru", user_id=user_id)
        session.commit()

        def resume(subject: str):
            imap = _sent_imap()
            smtp = FakeSmtpTransport(imap=imap, sent_folder=SENT_FOLDER)
            tools = _tools_mail(session, user_id, smtp, imap)
            gateway = ToolExecutionGateway()
            args = gateway.execute(
                tools,
                "send_email",
                _mail_args(provider="yandex", subject=subject),
                context=ExecutionContext.INTERACTIVE_ASSISTANT,
            ).staged_action["arguments"]
            claim = SessionLocal()
            claim.add(
                ExternalActionAttempt(
                    user_id=user_id,
                    operation_id=args["operation_id"],
                    tool_name="send_email",
                    state=ATTEMPT_STARTED,
                    started_at=started_at,
                )
            )
            claim.commit()
            claim.close()
            return gateway, tools, smtp, imap, args

        gateway, tools, smtp, imap, args = resume("In window")
        imap.add_message(
            SENT_FOLDER,
            11,
            _tagged_sent_bytes(args, date_header="01 Jan 2000 00:00:00 +0000"),
            internaldate=started_at,
        )
        in_window = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert in_window.success is True
        assert in_window.output["changed"] is False
        assert smtp.send_calls == []
        assert imap.fetch_calls == [11]

        gateway, tools, smtp, imap, args = resume("Below")
        imap.add_message(
            SENT_FOLDER,
            12,
            _tagged_sent_bytes(args),
            internaldate=window_start - timedelta(seconds=1),
        )
        below = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert below.success is False
        assert smtp.send_calls == []
        assert imap.fetch_calls == []

        gateway, tools, smtp, imap, args = resume("Above")
        imap.add_message(
            SENT_FOLDER,
            13,
            _tagged_sent_bytes(args),
            internaldate=window_end + timedelta(seconds=1),
        )
        above = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert above.success is False
        assert smtp.send_calls == []
        assert imap.fetch_calls == []

        gateway, tools, smtp, imap, args = resume("Low bound")
        imap.add_message(SENT_FOLDER, 14, _tagged_sent_bytes(args), internaldate=window_start)
        low = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert low.success is True
        assert smtp.send_calls == []

        gateway, tools, smtp, imap, args = resume("High bound")
        imap.add_message(SENT_FOLDER, 15, _tagged_sent_bytes(args), internaldate=window_end)
        high = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert high.success is True
        assert smtp.send_calls == []

        gateway, tools, smtp, imap, args = resume("Mixed")
        tagged = _tagged_sent_bytes(args)
        imap.add_message(
            SENT_FOLDER, 16, tagged, internaldate=window_start - timedelta(hours=1)
        )
        imap.add_message(SENT_FOLDER, 17, tagged, internaldate=started_at)
        mixed = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert mixed.success is True
        assert mixed.output["changed"] is False
        assert smtp.send_calls == []
        assert imap.fetch_calls == [17]

        gateway, tools, smtp, imap, args = resume("Overflow")
        for index in range(1, 202):
            imap.add_message(SENT_FOLDER, index, b"From: a@b.c\r\nSubject: x\r\n\r\nx")
        overflow = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert overflow.success is False
        assert smtp.send_calls == []
        assert imap.fetch_calls == []
        assert imap.internaldate_fetch_calls == []
        assert imap.window_search_calls[0]["max_results"] == 200

        gateway, tools, smtp, imap, args = resume("Mismatch")
        imap.add_message(
            SENT_FOLDER,
            18,
            _tagged_sent_bytes(args, subject="other"),
            internaldate=started_at,
        )
        mismatch = gateway.execute(
            tools, "send_email", args, context=ExecutionContext.APPROVED_ACTION_PLAN
        )
        assert mismatch.success is False
        assert "does not match" in (mismatch.error or "")
        assert smtp.send_calls == []
    finally:
        session.execute(delete(ExternalActionAttempt).where(ExternalActionAttempt.user_id == user_id))
        session.execute(delete(PendingActionPlan).where(PendingActionPlan.user_id == user_id))
        session.commit()
        session.close()


def test_send_email_input_rejects_unknown_provider():
    with pytest.raises(PydanticValidationError):
        SendEmailInput.model_validate({**_mail_args(), "provider": "gmail"})
    with pytest.raises(PydanticValidationError):
        CreateCalendarEventCanonicalInput.model_validate(
            {
                **_event_args(),
                "account_email": "a@b.c",
                "operation_id": "deadbeefdeadbeefdeadbeefdeadbeef",
                "provider": "yandex",
                "attendees": ["x@y.z"],
            }
        )
