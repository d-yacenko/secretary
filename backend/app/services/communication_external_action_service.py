"""Bounded Mattermost send_message execution after approval."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.mattermost.credentials import MattermostAccountStore
from app.connectors.mattermost.errors import (
    MattermostConfigurationError,
    MattermostSecurityError,
    MattermostWriteDefiniteError,
    MattermostWriteUncertainError,
)
from app.connectors.mattermost.materialize import MattermostObjectMaterializer
from app.connectors.mattermost.normalize import (
    MattermostChannelContext,
    build_external_id,
    normalize_server_url,
    parse_allowed_base_urls,
    validate_server_url_allowlist,
)
from app.connectors.mattermost.transport import MattermostHttpTransport, MattermostTransport
from app.core.config import settings
from app.db.models import ExternalActionAttempt, MattermostAccount, Object
from app.db.session import SessionLocal
from app.domain.object_visibility import is_object_hidden_from_active_reads
from app.services.provenance import REJECTED_STATE
from app.tools.schemas import (
    SendMessageCanonicalInput,
    SendMessageInput,
    SendMessageOutput,
    ToolError,
)

ATTEMPT_STARTED = "started"
ATTEMPT_SUCCEEDED = "succeeded"
ATTEMPT_FAILED_DEFINITE = "failed_definite"
ATTEMPT_UNCERTAIN = "uncertain"

SEND_MESSAGE_TOOL_NAME = "send_message"
PENDING_POST_ID_PREFIX = "secretary:"

_UNCERTAIN_DELIVERY_MESSAGE = "could not confirm message delivery; not retrying send"
_FAILED_DEFINITE_MESSAGE = "message send previously failed; create a new plan"
_KIND_REQUIRED = "chat_message"
_PROVIDER_REQUIRED = "mattermost"


def generate_operation_id() -> str:
    return uuid4().hex


def pending_post_id_from_operation_id(operation_id: str) -> str:
    compact = operation_id.replace("-", "").lower().strip()
    if len(compact) < 5 or len(compact) > 1024:
        raise ToolError("invalid operation_id")
    return f"{PENDING_POST_ID_PREFIX}{compact}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_body(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class CommunicationExternalActionService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        *,
        transport: MattermostTransport | None = None,
        attempt_session_factory=SessionLocal,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._transport = transport
        self._attempt_session_factory = attempt_session_factory
        self._materializer = MattermostObjectMaterializer(session)

    def prepare_send_message(self, payload: SendMessageInput) -> SendMessageCanonicalInput:
        if payload.conversation_object_id is not None:
            mode = "compose"
            anchor_id = payload.conversation_object_id
        else:
            mode = "reply"
            if payload.reply_to_object_id is None:
                raise ToolError("exactly one of conversation_object_id or reply_to_object_id is required")
            anchor_id = payload.reply_to_object_id

        obj = self._load_anchor(anchor_id)
        route = self._validated_route(obj)
        root_id = None
        if mode == "reply":
            root_id = route["root_id"]

        operation_id = generate_operation_id()
        return SendMessageCanonicalInput(
            provider="mattermost",
            mode=mode,
            account_id=route["account_id"],
            server_url=route["server_url"],
            channel_id=route["channel_id"],
            channel_type=route["channel_type"],
            channel_name=route["channel_name"],
            channel_display_name=route["channel_display_name"],
            anchor_object_id=obj.id,
            source_post_id=route["post_id"],
            root_id=root_id,
            body=payload.body,
            operation_id=operation_id,
            pending_post_id=pending_post_id_from_operation_id(operation_id),
        )

    def send_message(self, payload: SendMessageCanonicalInput) -> SendMessageOutput:
        expected_pending = pending_post_id_from_operation_id(payload.operation_id)
        if payload.pending_post_id != expected_pending:
            raise ToolError("pending_post_id does not match operation_id")
        if payload.provider != "mattermost":
            raise ToolError("unsupported send_message provider")
        account = self._require_account(payload.account_id)
        self._assert_frozen_account(account, payload)
        attempt, claimed = self._claim_started(payload.operation_id)
        if not claimed:
            return self._resume_existing_attempt(payload, attempt)
        return self._write_once(payload, account)

    def _load_anchor(self, object_id: UUID) -> Object:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise ToolError("object not found")
        if is_object_hidden_from_active_reads(obj):
            raise ToolError("object is deleted")
        if obj.state == REJECTED_STATE:
            raise ToolError("object is rejected")
        if obj.kind != _KIND_REQUIRED:
            raise ToolError("anchor must be a chat_message")
        if obj.provider != _PROVIDER_REQUIRED:
            raise ToolError("anchor provider is not mattermost")
        return obj

    def _validated_route(self, obj: Object) -> dict[str, Any]:
        meta = dict(obj.metadata_ or {})
        raw_account_id = meta.get("account_id")
        try:
            account_id = UUID(str(raw_account_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ToolError("malformed Mattermost account_id") from exc

        post_id = str(meta.get("post_id") or "").strip()
        channel_id = str(meta.get("channel_id") or "").strip()
        raw_server = str(meta.get("server_url") or "").strip()
        if not post_id or not channel_id or not raw_server:
            raise ToolError("malformed Mattermost routing metadata")

        try:
            normalized_server = normalize_server_url(raw_server)
            allowed = parse_allowed_base_urls(settings.mattermost_allowed_base_urls)
            validate_server_url_allowlist(normalized_server, allowed)
        except MattermostSecurityError as exc:
            raise ToolError(exc.message) from exc

        account = self._require_account(account_id)
        if account.server_url != normalized_server:
            raise ToolError("Mattermost server_url does not match the connected account")

        expected_external_id = build_external_id(normalized_server, post_id)
        if obj.external_id != expected_external_id:
            raise ToolError("Mattermost external_id does not match post routing")

        raw_root = str(meta.get("root_id") or "").strip() or None
        return {
            "account_id": account.id,
            "server_url": account.server_url,
            "channel_id": channel_id,
            "post_id": post_id,
            "root_id": raw_root,
            "channel_type": str(meta.get("channel_type") or "").strip() or None,
            "channel_name": str(meta.get("channel_name") or "").strip() or None,
            "channel_display_name": str(meta.get("channel_display_name") or "").strip() or None,
        }

    def _require_account(self, account_id: UUID) -> MattermostAccount:
        account = self._account_store().get_by_id_for_user(account_id, self._user_id)
        if account is None:
            raise ToolError("Mattermost account is not connected")
        return account

    def _assert_frozen_account(self, account: MattermostAccount, payload: SendMessageCanonicalInput) -> None:
        if account.id != payload.account_id or account.user_id != self._user_id:
            raise ToolError("Mattermost account is not connected")
        try:
            allowed = parse_allowed_base_urls(settings.mattermost_allowed_base_urls)
            validate_server_url_allowlist(account.server_url, allowed)
        except MattermostSecurityError as exc:
            raise ToolError(exc.message) from exc
        if account.server_url != payload.server_url:
            raise ToolError("Mattermost server_url does not match the connected account")

    def _write_once(
        self,
        payload: SendMessageCanonicalInput,
        account: MattermostAccount,
    ) -> SendMessageOutput:
        owns_transport = False
        transport = self._transport
        if transport is None:
            try:
                transport = self._open_http_transport(account)
            except (ToolError, MattermostConfigurationError) as exc:
                return self._definite_failure(payload, exc.message)
            owns_transport = True
        try:
            try:
                created = transport.create_post(
                    channel_id=payload.channel_id,
                    message=payload.body,
                    pending_post_id=payload.pending_post_id,
                    root_id=payload.root_id,
                )
            except MattermostSecurityError as exc:
                return self._definite_failure(payload, exc.message)
            except MattermostWriteDefiniteError as exc:
                return self._definite_failure(payload, exc.message)
            except MattermostWriteUncertainError as exc:
                return self._after_uncertain_write(payload, exc.message)
        finally:
            if owns_transport:
                transport.close()

        mismatch = self._success_mismatch(payload, account, created)
        if mismatch is not None:
            return self._after_uncertain_write(payload, mismatch)

        provider_id = str(created.get("id") or "").strip() or None
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_SUCCEEDED,
            provider_external_id=provider_id,
            delivery_status="sent",
        )
        obj = self._materialize_created(payload, account, created)
        return self._output(
            payload,
            provider_id,
            object_id=obj.id if obj is not None else None,
            delivery_status="sent",
            changed=True,
        )

    def _resume_existing_attempt(
        self,
        payload: SendMessageCanonicalInput,
        attempt: ExternalActionAttempt,
    ) -> SendMessageOutput:
        if attempt.state == ATTEMPT_SUCCEEDED:
            return self._output(
                payload,
                attempt.provider_external_id,
                object_id=self._object_id_from_attempt(payload, attempt),
                delivery_status="already_sent",
                changed=False,
            )
        if attempt.state == ATTEMPT_FAILED_DEFINITE:
            raise ToolError(_FAILED_DEFINITE_MESSAGE)
        matched = self._reconcile_local(payload)
        if matched is not None:
            provider_id = str((matched.metadata_ or {}).get("post_id") or "").strip() or None
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_SUCCEEDED,
                provider_external_id=provider_id,
                delivery_status="already_sent",
            )
            return self._output(
                payload,
                provider_id,
                object_id=matched.id,
                delivery_status="already_sent",
                changed=False,
            )
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_UNCERTAIN,
            error=_UNCERTAIN_DELIVERY_MESSAGE,
        )
        raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE)

    def _after_uncertain_write(self, payload: SendMessageCanonicalInput, error: str) -> SendMessageOutput:
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_UNCERTAIN,
            error=error or _UNCERTAIN_DELIVERY_MESSAGE,
        )
        matched = self._reconcile_local(payload)
        if matched is not None:
            provider_id = str((matched.metadata_ or {}).get("post_id") or "").strip() or None
            self._persist_attempt_state(
                payload.operation_id,
                ATTEMPT_SUCCEEDED,
                provider_external_id=provider_id,
                delivery_status="already_sent",
            )
            return self._output(
                payload,
                provider_id,
                object_id=matched.id,
                delivery_status="already_sent",
                changed=False,
            )
        raise ToolError(_UNCERTAIN_DELIVERY_MESSAGE)

    def _definite_failure(self, payload: SendMessageCanonicalInput, error: str) -> SendMessageOutput:
        self._persist_attempt_state(
            payload.operation_id,
            ATTEMPT_FAILED_DEFINITE,
            error=error,
        )
        raise ToolError(error or "Mattermost write rejected")

    def _reconcile_local(self, payload: SendMessageCanonicalInput) -> Object | None:
        return self._materializer.find_by_pending_post_id(
            user_id=self._user_id,
            account_id=payload.account_id,
            channel_id=payload.channel_id,
            pending_post_id=payload.pending_post_id,
        )

    def _success_mismatch(
        self,
        payload: SendMessageCanonicalInput,
        account: MattermostAccount,
        created: dict[str, Any],
    ) -> str | None:
        if not isinstance(created, dict):
            return _UNCERTAIN_DELIVERY_MESSAGE
        post_id = str(created.get("id") or "").strip()
        if not post_id:
            return _UNCERTAIN_DELIVERY_MESSAGE
        returned_channel = str(created.get("channel_id") or "").strip()
        if returned_channel != payload.channel_id:
            return _UNCERTAIN_DELIVERY_MESSAGE
        returned_message = created.get("message")
        if not isinstance(returned_message, str) or _normalize_body(returned_message) != payload.body:
            return _UNCERTAIN_DELIVERY_MESSAGE
        returned_user = str(created.get("user_id") or "").strip()
        if returned_user and returned_user != account.remote_user_id:
            return _UNCERTAIN_DELIVERY_MESSAGE
        returned_pending = str(created.get("pending_post_id") or "").strip()
        if returned_pending and returned_pending != payload.pending_post_id:
            return _UNCERTAIN_DELIVERY_MESSAGE
        if payload.root_id:
            returned_root = str(created.get("root_id") or "").strip()
            if returned_root != payload.root_id:
                return _UNCERTAIN_DELIVERY_MESSAGE
        return None

    def _materialize_created(
        self,
        payload: SendMessageCanonicalInput,
        account: MattermostAccount,
        created: dict[str, Any],
    ) -> Object | None:
        channel = MattermostChannelContext(
            channel_id=payload.channel_id,
            channel_name=payload.channel_name,
            channel_display_name=payload.channel_display_name,
            channel_type=payload.channel_type,
            team_id=None,
            team_name=None,
            team_display_name=None,
        )
        author = {
            "id": account.remote_user_id,
            "username": account.username,
            "display_name": account.display_name,
        }
        result = self._materializer.upsert_post(
            user_id=self._user_id,
            normalized_server_url=payload.server_url,
            account_id=account.id,
            channel=channel,
            post=created,
            author=author,
            skip_hidden=False,
        )
        return result.obj

    def _object_id_from_attempt(
        self,
        payload: SendMessageCanonicalInput,
        attempt: ExternalActionAttempt,
    ) -> UUID | None:
        provider_id = str(attempt.provider_external_id or "").strip()
        if not provider_id:
            matched = self._reconcile_local(payload)
            return matched.id if matched is not None else None
        existing = self._materializer.find_existing(
            self._user_id,
            build_external_id(payload.server_url, provider_id),
        )
        return existing.id if existing is not None else None

    def _open_http_transport(self, account: MattermostAccount) -> MattermostHttpTransport:
        if not settings.secretary_credential_key:
            raise ToolError("credentials are not configured")
        token = self._account_store().get_access_token(account)
        return MattermostHttpTransport(
            base_url=account.server_url,
            access_token=token,
        )

    def _account_store(self) -> MattermostAccountStore:
        if not settings.secretary_credential_key:
            raise ToolError("credentials are not configured")
        return MattermostAccountStore(
            self._session,
            MattermostAccountStore.build_encryption(settings.secretary_credential_key),
        )

    def _claim_started(self, operation_id: str) -> tuple[ExternalActionAttempt, bool]:
        session = self._attempt_session_factory()
        try:
            nested = session.begin_nested()
            try:
                attempt = ExternalActionAttempt(
                    user_id=self._user_id,
                    operation_id=operation_id,
                    tool_name=SEND_MESSAGE_TOOL_NAME,
                    state=ATTEMPT_STARTED,
                    started_at=_utcnow(),
                )
                session.add(attempt)
                session.flush()
                nested.commit()
            except IntegrityError:
                nested.rollback()
                existing = session.scalar(
                    select(ExternalActionAttempt).where(
                        ExternalActionAttempt.user_id == self._user_id,
                        ExternalActionAttempt.operation_id == operation_id,
                    )
                )
                if existing is None:
                    raise ToolError("failed to claim send_message operation")
                return existing, False
            session.commit()
            session.refresh(attempt)
            return attempt, True
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
            if attempt.state == ATTEMPT_FAILED_DEFINITE and state != ATTEMPT_FAILED_DEFINITE:
                return
            metadata = dict(attempt.result_metadata or {})
            if delivery_status:
                metadata["delivery_status"] = delivery_status
            if error:
                metadata["error"] = error[:500]
            if attempt.state == ATTEMPT_SUCCEEDED and state != ATTEMPT_SUCCEEDED:
                attempt.result_metadata = metadata
                flag_modified(attempt, "result_metadata")
                session.commit()
                return
            attempt.state = state
            attempt.result_metadata = metadata
            flag_modified(attempt, "result_metadata")
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

    def _output(
        self,
        payload: SendMessageCanonicalInput,
        provider_message_id: str | None,
        *,
        object_id: UUID | None,
        delivery_status: str,
        changed: bool,
    ) -> SendMessageOutput:
        return SendMessageOutput(
            provider="mattermost",
            mode=payload.mode,
            provider_message_id=provider_message_id,
            object_id=object_id,
            delivery_status=delivery_status,  # type: ignore[arg-type]
            changed=changed,
        )
