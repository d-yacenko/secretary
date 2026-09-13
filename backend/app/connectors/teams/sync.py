from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.teams.account_store import TeamsAccountStore
from app.connectors.teams.constants import (
    CHATS_STATE_KEY,
    DEFAULT_MAX_CHAT_PAGES,
    DEFAULT_MAX_MESSAGE_PAGES_PER_CHAT,
    DEFAULT_SYNC_OVERLAP_SECONDS,
    MAX_MAX_CHAT_PAGES,
    MAX_MAX_MESSAGE_PAGES_PER_CHAT,
    MAX_SYNC_OVERLAP_SECONDS,
    SYNC_START_AT_KEY,
    TOKEN_REFRESH_SKEW_SECONDS,
)
from app.connectors.teams.errors import TeamsConfigurationError, TeamsOAuthError, TeamsSyncError
from app.connectors.teams.materialize import TeamsObjectMaterializer
from app.connectors.teams.normalize import accepted_chat_type, display_title_for_chat, parse_graph_datetime
from app.connectors.teams.oauth_service import TeamsOAuthService, parse_token_expiry
from app.connectors.teams.transport import TeamsHttpTransport, TeamsTransport
from app.core.config import settings
from app.db.models import TeamsAccount
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _SyncTotals:
    synchronized: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    jobs_enqueued: int = 0


class TeamsSyncService:
    def __init__(
        self,
        session: Session,
        account_store: TeamsAccountStore,
        job_queue: JobQueueService,
        *,
        overlap_seconds: int = DEFAULT_SYNC_OVERLAP_SECONDS,
        max_chat_pages: int = DEFAULT_MAX_CHAT_PAGES,
        max_message_pages_per_chat: int = DEFAULT_MAX_MESSAGE_PAGES_PER_CHAT,
        transport: TeamsTransport | None = None,
        oauth_service: TeamsOAuthService | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._job_queue = job_queue
        self._overlap_seconds = min(max(overlap_seconds, 0), MAX_SYNC_OVERLAP_SECONDS)
        self._max_chat_pages = min(max(max_chat_pages, 1), MAX_MAX_CHAT_PAGES)
        self._max_message_pages_per_chat = min(
            max(max_message_pages_per_chat, 1), MAX_MAX_MESSAGE_PAGES_PER_CHAT
        )
        self._transport = transport
        self._oauth_service = oauth_service
        self._now_factory = now_factory or utcnow
        self._materializer = TeamsObjectMaterializer(session)

    def sync_account(self, account_id: UUID, user_id: UUID) -> dict[str, Any]:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise TeamsConfigurationError("Teams account not found")
        transport, owns = self._open_transport(account)
        try:
            return self._sync_with_transport(account, transport)
        finally:
            if owns:
                transport.close()

    def _sync_with_transport(self, account: TeamsAccount, transport: TeamsTransport) -> dict[str, Any]:
        state = dict(account.sync_state or {})
        sync_start = parse_graph_datetime(state.get(SYNC_START_AT_KEY))
        if sync_start is None:
            raise TeamsSyncError("Teams sync start boundary is missing")
        chats_state = dict(state.get(CHATS_STATE_KEY) or {})
        totals = _SyncTotals()
        chats = self._list_accepted_chats(transport, account.microsoft_user_id)
        for chat in chats:
            chat_id = str(chat.get("id") or "").strip()
            chat_type = accepted_chat_type(chat)
            if not chat_id or chat_type is None:
                continue
            title = display_title_for_chat(chat, self_user_id=account.microsoft_user_id)
            chat_entry = dict(chats_state.get(chat_id) or {})
            watermark = parse_graph_datetime(chat_entry.get("last_created_at"))
            floor = watermark - timedelta(seconds=self._overlap_seconds) if watermark else sync_start
            created, pages_exhausted = self._sync_chat_messages(
                account=account,
                transport=transport,
                chat_id=chat_id,
                chat_type=chat_type,
                chat_display_title=title,
                floor=floor,
                totals=totals,
            )
            if pages_exhausted:
                raise TeamsSyncError("Teams sync bound reached before all qualifying messages were processed")
            newest = created[0] if created else None
            if newest is not None:
                chat_entry["last_created_at"] = newest.isoformat()
            chat_entry["chat_type"] = chat_type
            chat_entry["display_title"] = title
            chats_state[chat_id] = chat_entry
        state[CHATS_STATE_KEY] = chats_state
        self._account_store.update_sync_state(account.id, account.user_id, state)
        self._session.commit()
        return {
            "synchronized": totals.synchronized,
            "created": totals.created,
            "updated": totals.updated,
            "unchanged": totals.unchanged,
            "jobs_enqueued": totals.jobs_enqueued,
        }

    def _list_accepted_chats(self, transport: TeamsTransport, self_user_id: str) -> list[dict[str, Any]]:
        chats: list[dict[str, Any]] = []
        next_url: str | None = None
        for _ in range(self._max_chat_pages):
            payload = transport.list_chats(next_url)
            values = payload.get("value") if isinstance(payload, dict) else None
            if not isinstance(values, list):
                raise TeamsSyncError("Teams chat list is malformed")
            for raw in values:
                if not isinstance(raw, dict):
                    continue
                chat_type = accepted_chat_type(raw)
                if chat_type is None:
                    continue
                chat_id = str(raw.get("id") or "").strip()
                if not chat_id:
                    continue
                if "members" not in raw:
                    raw = transport.get_chat(chat_id)
                chats.append(raw)
            next_link = payload.get("@odata.nextLink") if isinstance(payload, dict) else None
            if not next_link:
                return chats
            next_url = str(next_link)
        raise TeamsSyncError("Teams chat list bound reached before all chats were processed")

    def _sync_chat_messages(
        self,
        *,
        account: TeamsAccount,
        transport: TeamsTransport,
        chat_id: str,
        chat_type: str,
        chat_display_title: str | None,
        floor: datetime,
        totals: _SyncTotals,
    ) -> tuple[list[datetime], bool]:
        created_at_values: list[datetime] = []
        next_url: str | None = None
        for page_index in range(self._max_message_pages_per_chat):
            payload = transport.list_chat_messages(chat_id, next_url)
            values = payload.get("value") if isinstance(payload, dict) else None
            if not isinstance(values, list):
                raise TeamsSyncError("Teams message list is malformed")
            page_had_qualifying = False
            older_than_floor = False
            for raw in values:
                if not isinstance(raw, dict):
                    continue
                created_at = parse_graph_datetime(raw.get("createdDateTime"))
                if created_at is None:
                    continue
                if created_at < floor:
                    older_than_floor = True
                    continue
                page_had_qualifying = True
                result = self._materializer.upsert_message(
                    user_id=account.user_id,
                    account_id=account.id,
                    tenant_id=account.tenant_id,
                    microsoft_user_id=account.microsoft_user_id,
                    chat_id=chat_id,
                    chat_type=chat_type,
                    chat_display_title=chat_display_title,
                    message=raw,
                )
                totals.synchronized += 1
                if result.change == "created":
                    totals.created += 1
                elif result.change == "updated":
                    totals.updated += 1
                else:
                    totals.unchanged += 1
                totals.jobs_enqueued += result.jobs_enqueued
                created_at_values.append(created_at)
            next_link = payload.get("@odata.nextLink") if isinstance(payload, dict) else None
            if older_than_floor or not next_link:
                return sorted(created_at_values, reverse=True), False
            if not page_had_qualifying and page_index == 0:
                return [], False
            next_url = str(next_link)
        return sorted(created_at_values, reverse=True), True

    def _open_transport(self, account: TeamsAccount) -> tuple[TeamsTransport, bool]:
        if self._transport is not None:
            return self._transport, False
        token = self._valid_access_token(account)
        return TeamsHttpTransport(token), True

    def _valid_access_token(self, account: TeamsAccount) -> str:
        now = self._now_factory()
        expiry = account.token_expiry
        if expiry is None or expiry - timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS) > now:
            return self._account_store.get_access_token(account)
        refresh_token = self._account_store.get_refresh_token(account)
        oauth = self._oauth_service or TeamsOAuthService(
            settings.microsoft_oauth_client_id,
            settings.microsoft_oauth_client_secret,
            settings.microsoft_redirect_uri,
        )
        payload = oauth.refresh_access_token(refresh_token)
        access_token = str(payload["access_token"])
        new_refresh = payload.get("refresh_token")
        self._account_store.update_tokens_from_refresh(
            account,
            access_token,
            str(new_refresh) if new_refresh else None,
            parse_token_expiry(payload.get("expires_in")),
        )
        self._session.commit()
        return access_token


def build_teams_sync_service(
    session: Session,
    *,
    credential_key: str,
    overlap_seconds: int = DEFAULT_SYNC_OVERLAP_SECONDS,
    transport: TeamsTransport | None = None,
    oauth_service: TeamsOAuthService | None = None,
) -> TeamsSyncService:
    if not credential_key:
        raise TeamsConfigurationError("credential encryption key is not configured")
    store = TeamsAccountStore(session, TeamsAccountStore.build_encryption(credential_key))
    return TeamsSyncService(
        session,
        store,
        JobQueueService(session),
        overlap_seconds=overlap_seconds,
        transport=transport,
        oauth_service=oauth_service,
    )
