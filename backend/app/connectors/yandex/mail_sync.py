from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.yandex.constants import (
    DEFAULT_MAIL_FOLDER,
    DEFAULT_SYNC_DAYS,
    DEFAULT_SYNC_LIMIT,
    MAX_SYNC_DAYS,
    MAX_SYNC_LIMIT,
)
from app.connectors.yandex.credentials import YandexMailAccountStore, YandexMailSyncSnapshot
from app.connectors.yandex.errors import YandexConnectorError
from app.connectors.yandex.imap_transport import ImaplibTransport, ImapTransport
from app.connectors.yandex.mail_normalize import build_external_id, normalize_imap_message
from app.db.models import Object
from app.services.job_queue_service import JobQueueService


def utcnow() -> datetime:
    return datetime.now(UTC)


class YandexMailSyncService:
    def __init__(
        self,
        session: Session,
        account_store: YandexMailAccountStore,
        job_queue: JobQueueService,
        sync_days: int = DEFAULT_SYNC_DAYS,
        default_limit: int = DEFAULT_SYNC_LIMIT,
        max_limit: int = MAX_SYNC_LIMIT,
        transport_factory: Callable[[YandexMailSyncSnapshot], ImapTransport] | None = None,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._job_queue = job_queue
        self._sync_days = min(max(sync_days, 1), MAX_SYNC_DAYS)
        self._default_limit = default_limit
        self._max_limit = max_limit
        self._transport_factory = transport_factory

    def sync_account(
        self,
        account_id: UUID,
        user_id: UUID,
        limit: int | None = None,
    ) -> dict[str, Any]:
        snapshot = self._account_store.load_sync_snapshot(account_id, user_id)
        if snapshot is None:
            raise YandexConnectorError("yandex mail account not found")

        effective_limit = limit if limit is not None else self._default_limit
        effective_limit = min(max(effective_limit, 1), self._max_limit)

        self._session.commit()

        transport = self._open_transport(snapshot)
        folder = DEFAULT_MAIL_FOLDER
        since_date = utcnow() - timedelta(days=self._sync_days)
        stored_state = dict(snapshot.sync_state)
        stored_uidvalidity = stored_state.get("inbox_uidvalidity")
        stored_last_uid = stored_state.get("inbox_last_uid")

        try:
            uidvalidity = transport.select_folder(folder)

            use_incremental = (
                stored_uidvalidity is not None
                and stored_uidvalidity == uidvalidity
                and stored_last_uid is not None
            )

            if use_incremental:
                candidate_uids = transport.search_uids_incremental(
                    folder=folder,
                    after_uid=int(stored_last_uid),
                    max_results=effective_limit,
                )
            else:
                candidate_uids = transport.search_uids_initial(
                    folder=folder,
                    since_date=since_date,
                    max_results=effective_limit,
                )

            known_external_ids = self._load_known_external_ids(
                snapshot.user_id,
                folder,
                uidvalidity,
                candidate_uids,
            )
            self._session.commit()

            created = 0
            updated = 0
            jobs_enqueued = 0
            synchronized = 0
            unchanged = 0
            max_processed_uid = int(stored_last_uid or 0) if use_incremental else 0

            for uid in candidate_uids:
                external_id = build_external_id(folder, uidvalidity, uid)
                if external_id in known_external_ids:
                    synchronized += 1
                    unchanged += 1
                    max_processed_uid = max(max_processed_uid, uid)
                    continue

                self._session.commit()
                raw_message = transport.fetch_message(folder, uid)
                normalized = normalize_imap_message(
                    raw_message,
                    folder=folder,
                    uid=uid,
                    uidvalidity=uidvalidity,
                )
                obj = Object(
                    user_id=snapshot.user_id,
                    kind=normalized["kind"],
                    provider=normalized["provider"],
                    external_id=normalized["external_id"],
                    origin=normalized["origin"],
                    state=normalized["state"],
                    title=normalized["title"],
                    body=normalized.get("body"),
                    metadata_=normalized["metadata"],
                    occurred_at=normalized.get("occurred_at"),
                )
                self._session.add(obj)
                self._session.flush()
                created += 1
                synchronized += 1
                max_processed_uid = max(max_processed_uid, uid)
                self._job_queue.enqueue(
                    "embed_object",
                    {"object_id": str(obj.id)},
                    user_id=snapshot.user_id,
                )
                jobs_enqueued += 1
                self._session.commit()

            account = self._account_store.get_by_id_for_user(account_id, user_id)
            if account is None:
                raise YandexConnectorError("yandex mail account not found")
            new_state = {
                "inbox_uidvalidity": uidvalidity,
                "inbox_last_uid": max_processed_uid,
            }
            self._account_store.update_sync_state(account, new_state)
            self._session.commit()

            return {
                "account_email": snapshot.email,
                "synchronized": synchronized,
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "jobs_enqueued": jobs_enqueued,
            }
        finally:
            if isinstance(transport, ImaplibTransport):
                transport.close()

    def _open_transport(self, snapshot: YandexMailSyncSnapshot) -> ImapTransport:
        if self._transport_factory is not None:
            return self._transport_factory(snapshot)
        return ImaplibTransport(
            host=snapshot.imap_host,
            port=snapshot.imap_port,
            email=snapshot.email,
            password=snapshot.app_password,
        )

    def _load_known_external_ids(
        self,
        user_id: UUID,
        folder: str,
        uidvalidity: int,
        uids: list[int],
    ) -> set[str]:
        if not uids:
            return set()
        external_ids = [build_external_id(folder, uidvalidity, uid) for uid in uids]
        rows = self._session.scalars(
            select(Object.external_id).where(
                Object.user_id == user_id,
                Object.provider == "yandex_mail",
                Object.kind == "email",
                Object.external_id.in_(external_ids),
            )
        )
        return {str(external_id) for external_id in rows if external_id is not None}


def build_yandex_mail_sync_service(
    session: Session,
    credential_key: str,
    sync_days: int,
    default_limit: int,
    max_limit: int,
    transport_factory: Callable[[YandexMailSyncSnapshot], ImapTransport] | None = None,
) -> YandexMailSyncService:
    account_store = YandexMailAccountStore(
        session,
        YandexMailAccountStore.build_encryption(credential_key),
    )
    job_queue = JobQueueService(session)
    return YandexMailSyncService(
        session=session,
        account_store=account_store,
        job_queue=job_queue,
        sync_days=sync_days,
        default_limit=default_limit,
        max_limit=max_limit,
        transport_factory=transport_factory,
    )
