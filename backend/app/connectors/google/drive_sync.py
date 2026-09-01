from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import (
    DRIVE_READONLY_SCOPE,
    GOOGLE_DRIVE_MAX_ITEMS_PER_RUN,
    GOOGLE_DRIVE_PROVIDER,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.drive_normalize import normalize_drive_file
from app.connectors.google.drive_transport import DriveTransport
from app.connectors.google.errors import GoogleConnectorError
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.db.models import Object
from app.services.job_queue_service import JobQueueService

DEFAULT_DRIVE_SYNC_STATE: dict[str, Any] = {
    "bootstrap_complete": False,
    "bootstrap_start_page_token": None,
    "bootstrap_page_token": None,
    "changes_page_token": None,
}


def normalize_drive_sync_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(DEFAULT_DRIVE_SYNC_STATE)
    if raw:
        for key in DEFAULT_DRIVE_SYNC_STATE:
            if key in raw:
                state[key] = raw[key]
    return state


@dataclass
class _SyncTotals:
    synchronized: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    tombstoned: int = 0
    jobs_enqueued: int = 0


class DriveSyncService:
    def __init__(
        self,
        session: Session,
        account_store: GoogleAccountStore,
        token_manager: GoogleTokenManager,
        transport: DriveTransport,
        job_queue: JobQueueService,
        max_items_per_run: int = GOOGLE_DRIVE_MAX_ITEMS_PER_RUN,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._token_manager = token_manager
        self._transport = transport
        self._job_queue = job_queue
        self._max_items_per_run = min(max(max_items_per_run, 1), GOOGLE_DRIVE_MAX_ITEMS_PER_RUN)

    def sync_account(self, account_id: UUID, user_id: UUID) -> dict[str, Any]:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise GoogleConnectorError("google account not found")
        if DRIVE_READONLY_SCOPE not in account.scopes:
            raise GoogleConnectorError("google drive scope not granted")

        account_email = account.email
        owner_user_id = account.user_id
        sync_state = normalize_drive_sync_state(account.drive_sync_state)

        self._session.commit()
        access_token = self._token_manager.get_valid_access_token(account_id, user_id)
        self._session.commit()

        owns_transport = self._should_close_transport()
        try:
            items_budget = self._max_items_per_run
            totals = _SyncTotals()

            if not sync_state["bootstrap_complete"]:
                items_budget, sync_state, batch = self._run_bootstrap(
                    access_token=access_token,
                    account_id=account_id,
                    user_id=user_id,
                    sync_state=sync_state,
                    owner_user_id=owner_user_id,
                    items_budget=items_budget,
                )
                self._merge_totals(totals, batch)
            else:
                changes_token = sync_state.get("changes_page_token")
                if changes_token:
                    items_budget, sync_state, batch = self._run_incremental(
                        access_token=access_token,
                        account_id=account_id,
                        user_id=user_id,
                        sync_state=sync_state,
                        owner_user_id=owner_user_id,
                        items_budget=items_budget,
                        changes_page_token=str(changes_token),
                    )
                    self._merge_totals(totals, batch)

            self._persist_sync_state(account_id, user_id, sync_state)

            return {
                "account_email": account_email,
                "synchronized": totals.synchronized,
                "created": totals.created,
                "updated": totals.updated,
                "unchanged": totals.unchanged,
                "tombstoned": totals.tombstoned,
                "jobs_enqueued": totals.jobs_enqueued,
            }
        finally:
            if owns_transport:
                self._transport.close()

    def _persist_sync_state(
        self,
        account_id: UUID,
        user_id: UUID,
        state: dict[str, Any],
    ) -> None:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise GoogleConnectorError("google account not found")
        self._account_store.update_drive_sync_state(account, state)
        self._session.commit()

    def _run_bootstrap(
        self,
        access_token: str,
        account_id: UUID,
        user_id: UUID,
        sync_state: dict[str, Any],
        owner_user_id: UUID,
        items_budget: int,
    ) -> tuple[int, dict[str, Any], _SyncTotals]:
        totals = _SyncTotals()
        state = dict(sync_state)

        if state.get("bootstrap_start_page_token") is None:
            start_token = self._transport.get_start_page_token(access_token)
            state["bootstrap_complete"] = False
            state["bootstrap_start_page_token"] = start_token
            state["bootstrap_page_token"] = None
            state["changes_page_token"] = None
            self._persist_sync_state(account_id, user_id, state)

        page_token = state.get("bootstrap_page_token")
        if page_token is not None:
            page_token = str(page_token)

        while items_budget > 0:
            page_size = items_budget
            page = self._transport.list_files(
                access_token=access_token,
                page_token=page_token,
                page_size=page_size,
            )
            if not page.files:
                if page.next_page_token is None:
                    state["bootstrap_complete"] = True
                    state["changes_page_token"] = state.get("bootstrap_start_page_token")
                    state["bootstrap_page_token"] = None
                    state["bootstrap_start_page_token"] = None
                    self._persist_sync_state(account_id, user_id, state)
                break

            processed_all = True
            for file_item in page.files:
                if items_budget <= 0:
                    processed_all = False
                    break
                change = self._upsert_file(owner_user_id, account_id, file_item)
                totals.synchronized += 1
                if change == "created":
                    totals.created += 1
                    totals.jobs_enqueued += 1
                elif change == "updated":
                    totals.updated += 1
                    totals.jobs_enqueued += 1
                elif change == "metadata_updated":
                    totals.updated += 1
                elif change == "tombstoned":
                    totals.tombstoned += 1
                elif change == "restored":
                    totals.updated += 1
                else:
                    totals.unchanged += 1
                items_budget -= 1
                self._session.commit()

            if not processed_all:
                break

            if page.next_page_token is None:
                state["bootstrap_complete"] = True
                state["changes_page_token"] = state.get("bootstrap_start_page_token")
                state["bootstrap_page_token"] = None
                state["bootstrap_start_page_token"] = None
                self._persist_sync_state(account_id, user_id, state)
                break

            page_token = page.next_page_token
            state["bootstrap_page_token"] = page_token
            self._persist_sync_state(account_id, user_id, state)

        return items_budget, state, totals

    def _run_incremental(
        self,
        access_token: str,
        account_id: UUID,
        user_id: UUID,
        sync_state: dict[str, Any],
        owner_user_id: UUID,
        items_budget: int,
        changes_page_token: str,
    ) -> tuple[int, dict[str, Any], _SyncTotals]:
        totals = _SyncTotals()
        state = dict(sync_state)
        page_token: str | None = changes_page_token
        pending_new_start: str | None = None

        while items_budget > 0 and page_token is not None:
            page_size = items_budget
            page = self._transport.list_changes(
                access_token=access_token,
                page_token=page_token,
                page_size=page_size,
            )

            if not page.changes:
                if page.next_page_token is None:
                    if page.new_start_page_token is not None:
                        state["changes_page_token"] = page.new_start_page_token
                        self._persist_sync_state(account_id, user_id, state)
                    break
                state["changes_page_token"] = page.next_page_token
                self._persist_sync_state(account_id, user_id, state)
                page_token = page.next_page_token
                if page.new_start_page_token is not None:
                    pending_new_start = page.new_start_page_token
                continue

            processed_all = True
            for change in page.changes:
                if items_budget <= 0:
                    processed_all = False
                    break
                change_result = self._process_change(
                    owner_user_id=owner_user_id,
                    account_id=account_id,
                    change=change,
                )
                totals.synchronized += 1
                if change_result == "created":
                    totals.created += 1
                    totals.jobs_enqueued += 1
                elif change_result == "updated":
                    totals.updated += 1
                    totals.jobs_enqueued += 1
                elif change_result == "metadata_updated":
                    totals.updated += 1
                elif change_result == "tombstoned":
                    totals.tombstoned += 1
                elif change_result == "restored":
                    totals.updated += 1
                else:
                    totals.unchanged += 1
                items_budget -= 1
                self._session.commit()

            if not processed_all:
                break

            if page.next_page_token is None:
                if page.new_start_page_token is not None:
                    state["changes_page_token"] = page.new_start_page_token
                    self._persist_sync_state(account_id, user_id, state)
                elif pending_new_start is not None:
                    state["changes_page_token"] = pending_new_start
                    self._persist_sync_state(account_id, user_id, state)
                break

            page_token = page.next_page_token
            state["changes_page_token"] = page_token
            self._persist_sync_state(account_id, user_id, state)
            if page.new_start_page_token is not None:
                pending_new_start = page.new_start_page_token

        return items_budget, state, totals

    def _process_change(
        self,
        owner_user_id: UUID,
        account_id: UUID,
        change: dict[str, Any],
    ) -> str:
        removed = bool(change.get("removed"))
        file_id = str(change.get("fileId") or "").strip()
        file_obj = change.get("file")

        if removed or not file_obj:
            if not file_id:
                return "unchanged"
            return self._tombstone_file(owner_user_id, file_id)

        if bool(file_obj.get("trashed")):
            tombstone_id = str(file_obj.get("id") or file_id).strip()
            if tombstone_id:
                return self._tombstone_file(owner_user_id, tombstone_id)
            return "unchanged"

        return self._upsert_file(owner_user_id, account_id, file_obj)

    def _upsert_file(
        self,
        user_id: UUID,
        account_id: UUID,
        file_item: dict[str, Any],
    ) -> str:
        normalized = normalize_drive_file(file_item, account_id)
        if normalized is None:
            return "unchanged"

        existing = self._find_existing(user_id, normalized["external_id"])
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
                canonical_uri=normalized.get("canonical_uri"),
                metadata_=normalized["metadata"],
                occurred_at=normalized.get("occurred_at"),
            )
            self._session.add(obj)
            self._session.flush()
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(obj.id)},
                user_id=user_id,
            )
            return "created"

        was_deleted = existing.status == "deleted"
        if not self._object_changed(existing, normalized):
            if was_deleted:
                existing.status = None
                return "restored"
            return "unchanged"

        semantic_changed = self._semantic_content_changed(existing, normalized)
        self._apply_normalized(existing, normalized)
        if was_deleted:
            existing.status = None
            if semantic_changed:
                self._job_queue.enqueue(
                    "embed_object",
                    {"object_id": str(existing.id)},
                    user_id=user_id,
                )
                return "restored"
            return "restored"

        if semantic_changed:
            self._job_queue.enqueue(
                "embed_object",
                {"object_id": str(existing.id)},
                user_id=user_id,
            )
            return "updated"
        return "metadata_updated"

    def _tombstone_file(self, user_id: UUID, file_id: str) -> str:
        existing = self._find_existing(user_id, file_id)
        if existing is None:
            return "unchanged"
        if existing.status == "deleted":
            return "unchanged"
        existing.status = "deleted"
        return "tombstoned"

    def _find_existing(self, user_id: UUID, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == user_id,
                Object.provider == GOOGLE_DRIVE_PROVIDER,
                Object.external_id == external_id,
            )
        )

    def _object_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.kind != normalized["kind"]:
            return True
        if obj.title != normalized["title"]:
            return True
        if obj.occurred_at != normalized.get("occurred_at"):
            return True
        if obj.canonical_uri != normalized.get("canonical_uri"):
            return True
        return obj.metadata_ != normalized["metadata"]

    def _semantic_content_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        return obj.title != normalized["title"]

    def _apply_normalized(self, obj: Object, normalized: dict[str, Any]) -> None:
        obj.kind = normalized["kind"]
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.canonical_uri = normalized.get("canonical_uri")
        obj.metadata_ = normalized["metadata"]
        obj.occurred_at = normalized.get("occurred_at")

    def _merge_totals(self, totals: _SyncTotals, batch: _SyncTotals) -> None:
        totals.synchronized += batch.synchronized
        totals.created += batch.created
        totals.updated += batch.updated
        totals.unchanged += batch.unchanged
        totals.tombstoned += batch.tombstoned
        totals.jobs_enqueued += batch.jobs_enqueued

    def _should_close_transport(self) -> bool:
        return True


def build_drive_sync_service(
    session: Session,
    credential_key: str,
    client_file: str,
    redirect_uri: str,
    max_items_per_run: int = GOOGLE_DRIVE_MAX_ITEMS_PER_RUN,
    http_client: Any | None = None,
) -> DriveSyncService:
    encryption = GoogleAccountStore.build_encryption(credential_key)
    account_store = GoogleAccountStore(session, encryption)
    oauth_service = GoogleOAuthService(client_file, redirect_uri, http_client=http_client)
    token_manager = GoogleTokenManager(session, account_store, oauth_service)
    transport = DriveTransport(http_client=http_client)
    job_queue = JobQueueService(session)
    return DriveSyncService(
        session=session,
        account_store=account_store,
        token_manager=token_manager,
        transport=transport,
        job_queue=job_queue,
        max_items_per_run=max_items_per_run,
    )
