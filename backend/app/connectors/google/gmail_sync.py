from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import DEFAULT_SYNC_DAYS, DEFAULT_SYNC_LIMIT, MAX_SYNC_LIMIT
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.errors import GoogleConnectorError
from app.connectors.google.gmail_normalize import normalize_gmail_message
from app.connectors.google.gmail_transport import GmailTransport, GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.db.models import GoogleAccount, Object
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GmailSyncService:
    def __init__(
        self,
        session: Session,
        account_store: GoogleAccountStore,
        token_manager: GoogleTokenManager,
        transport: GmailTransport,
        job_queue: JobQueueService,
        sync_days: int = DEFAULT_SYNC_DAYS,
        default_limit: int = DEFAULT_SYNC_LIMIT,
        max_limit: int = MAX_SYNC_LIMIT,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._token_manager = token_manager
        self._transport = transport
        self._job_queue = job_queue
        self._sync_days = sync_days
        self._default_limit = default_limit
        self._max_limit = max_limit

    def sync_account(
        self,
        account_id: UUID,
        limit: int | None = None,
    ) -> dict[str, Any]:
        account = self._account_store.get_by_id(account_id)
        if account is None:
            raise GoogleConnectorError("google account not found")

        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(effective_limit, 1), self._max_limit)

        access_token = self._token_manager.get_valid_access_token(account)
        self._session.commit()

        after_date = (utcnow() - timedelta(days=self._sync_days)).strftime("%Y/%m/%d")
        query = f"after:{after_date}"
        message_ids = self._transport.list_message_ids(
            access_token=access_token,
            user_id="me",
            query=query,
            max_results=effective_limit,
        )

        created = 0
        updated = 0
        jobs_enqueued = 0
        synchronized = 0

        for message_id in message_ids:
            raw_message = self._transport.get_message(access_token, "me", message_id)
            normalized = normalize_gmail_message(raw_message)
            existing = self._session.scalar(
                select(Object).where(
                    Object.provider == "gmail",
                    Object.kind == "email",
                    Object.external_id == normalized["external_id"],
                )
            )
            if existing is None:
                obj = Object(
                    kind=normalized["kind"],
                    provider=normalized["provider"],
                    external_id=normalized["external_id"],
                    origin=normalized["origin"],
                    state=normalized["state"],
                    title=normalized["title"],
                    metadata_=normalized["metadata"],
                )
                self._session.add(obj)
                self._session.flush()
                created += 1
                self._job_queue.enqueue("embed_object", {"object_id": str(obj.id)})
                jobs_enqueued += 1
            else:
                changed = self._apply_update(existing, normalized)
                if changed:
                    updated += 1
                    self._job_queue.enqueue("embed_object", {"object_id": str(existing.id)})
                    jobs_enqueued += 1
            synchronized += 1
            self._session.commit()

        return {
            "account_email": account.email,
            "synchronized": synchronized,
            "created": created,
            "updated": updated,
            "jobs_enqueued": jobs_enqueued,
        }

    def _apply_update(self, obj: Object, normalized: dict[str, Any]) -> bool:
        changed = False
        if obj.title != normalized["title"]:
            obj.title = normalized["title"]
            changed = True
        if obj.metadata_ != normalized["metadata"]:
            obj.metadata_ = normalized["metadata"]
            changed = True
        if obj.state != normalized["state"]:
            obj.state = normalized["state"]
            changed = True
        if changed:
            obj.updated_at = utcnow()
            self._session.flush()
        return changed


def build_gmail_sync_service(
    session: Session,
    credential_key: str,
    client_file: str,
    redirect_uri: str,
    sync_days: int,
    default_limit: int,
    max_limit: int,
    http_client: Any | None = None,
) -> GmailSyncService:
    encryption = GoogleAccountStore.build_encryption(credential_key)
    account_store = GoogleAccountStore(session, encryption)
    oauth_service = GoogleOAuthService(client_file, redirect_uri, http_client=http_client)
    token_manager = GoogleTokenManager(account_store, oauth_service)
    transport = GmailTransport(http_client=http_client)
    job_queue = JobQueueService(session)
    return GmailSyncService(
        session=session,
        account_store=account_store,
        token_manager=token_manager,
        transport=transport,
        job_queue=job_queue,
        sync_days=sync_days,
        default_limit=default_limit,
        max_limit=max_limit,
    )
