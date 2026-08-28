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
from app.db.models import Object
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
        user_id: UUID,
        limit: int | None = None,
    ) -> dict[str, Any]:
        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise GoogleConnectorError("google account not found")

        account_email = account.email
        owner_user_id = account.user_id
        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(effective_limit, 1), self._max_limit)

        self._session.commit()
        access_token = self._token_manager.get_valid_access_token(account_id, user_id)
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
        unchanged = 0

        for message_id in message_ids:
            self._session.commit()
            raw_message = self._transport.get_message(access_token, "me", message_id)
            normalized = normalize_gmail_message(raw_message)
            existing = self._find_existing_gmail_object(
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
                    metadata_=normalized["metadata"],
                )
                self._session.add(obj)
                self._session.flush()
                created += 1
                synchronized += 1
                self._job_queue.enqueue(
                    "embed_object",
                    {"object_id": str(obj.id)},
                    user_id=owner_user_id,
                )
                jobs_enqueued += 1
                self._session.commit()
                continue

            if self._gmail_object_changed(existing, normalized):
                self._apply_normalized_gmail_object(existing, normalized)
                updated += 1
                synchronized += 1
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
                self._session.commit()

        return {
            "account_email": account_email,
            "synchronized": synchronized,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "jobs_enqueued": jobs_enqueued,
        }

    def _find_existing_gmail_object(self, user_id: UUID, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == user_id,
                Object.provider == "gmail",
                Object.kind == "email",
                Object.external_id == external_id,
            )
        )

    def _gmail_object_changed(self, obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.title != normalized["title"]:
            return True
        if obj.body != normalized.get("body"):
            return True
        if obj.metadata_ != normalized["metadata"]:
            return True
        return False

    def _apply_normalized_gmail_object(self, obj: Object, normalized: dict[str, Any]) -> None:
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.metadata_ = normalized["metadata"]


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
    token_manager = GoogleTokenManager(session, account_store, oauth_service)
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
