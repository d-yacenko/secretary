from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import CALENDAR_READONLY_SCOPE, GMAIL_READONLY_SCOPE
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.core.config import settings
from app.db.models import GoogleAccount, Job, YandexCalendarAccount, YandexMailAccount
from app.jobs.constants import (
    JOB_STATUS_FAILED,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
    JOB_TYPE_SYNC_YANDEX_CALENDAR,
    JOB_TYPE_SYNC_YANDEX_MAIL,
)
from app.services.job_queue_service import JobQueueService, utcnow


class SourceSyncScheduler:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._queue = JobQueueService(session)

    def run_maintenance(self) -> None:
        if not settings.secretary_credential_key:
            return
        encryption = CredentialEncryption(settings.secretary_credential_key)
        self._maintain_google_accounts(GoogleAccountStore(self._session, encryption))
        self._maintain_yandex_mail_accounts(
            YandexMailAccountStore(self._session, encryption)
        )
        self._maintain_yandex_calendar_accounts(
            YandexCalendarAccountStore(self._session, encryption)
        )
        self._rearm_failed_recurring_jobs()

    def trigger_all_for_user(self, user_id: UUID) -> list[str]:
        triggered: list[str] = []
        if not settings.secretary_credential_key:
            return triggered
        encryption = CredentialEncryption(settings.secretary_credential_key)
        google_store = GoogleAccountStore(self._session, encryption)
        for account in google_store.list_accounts(user_id):
            scopes = set(account.scopes or [])
            if GMAIL_READONLY_SCOPE in scopes and self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_GOOGLE_GMAIL, account.id
            ):
                triggered.append(f"gmail:{account.id}")
            if CALENDAR_READONLY_SCOPE in scopes and self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_GOOGLE_CALENDAR, account.id
            ):
                triggered.append(f"google_calendar:{account.id}")
        yandex_mail_store = YandexMailAccountStore(self._session, encryption)
        for account in yandex_mail_store.list_accounts(user_id):
            if self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_YANDEX_MAIL, account.id
            ):
                triggered.append(f"yandex_mail:{account.id}")
        yandex_calendar_store = YandexCalendarAccountStore(self._session, encryption)
        for account in yandex_calendar_store.list_accounts(user_id):
            if self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_YANDEX_CALENDAR, account.id
            ):
                triggered.append(f"yandex_calendar:{account.id}")
        return triggered

    def _maintain_google_accounts(self, store: GoogleAccountStore) -> None:
        accounts = list(self._session.scalars(select(GoogleAccount)))
        for account in accounts:
            scopes = set(account.scopes or [])
            user_id = account.user_id
            if GMAIL_READONLY_SCOPE in scopes:
                self._queue.ensure_recurring_source_job(
                    JOB_TYPE_SYNC_GOOGLE_GMAIL,
                    account.id,
                    user_id,
                )
            if CALENDAR_READONLY_SCOPE in scopes:
                self._queue.ensure_recurring_source_job(
                    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
                    account.id,
                    user_id,
                )

    def _maintain_yandex_mail_accounts(self, store: YandexMailAccountStore) -> None:
        accounts = list(self._session.scalars(select(YandexMailAccount)))
        for account in accounts:
            self._queue.ensure_recurring_source_job(
                JOB_TYPE_SYNC_YANDEX_MAIL,
                account.id,
                account.user_id,
            )

    def _maintain_yandex_calendar_accounts(self, store: YandexCalendarAccountStore) -> None:
        accounts = list(self._session.scalars(select(YandexCalendarAccount)))
        for account in accounts:
            self._queue.ensure_recurring_source_job(
                JOB_TYPE_SYNC_YANDEX_CALENDAR,
                account.id,
                account.user_id,
            )

    def _rearm_failed_recurring_jobs(self) -> None:
        now = utcnow()
        failed_jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.type.in_(
                        (
                            JOB_TYPE_SYNC_GOOGLE_GMAIL,
                            JOB_TYPE_SYNC_GOOGLE_CALENDAR,
                            JOB_TYPE_SYNC_YANDEX_MAIL,
                            JOB_TYPE_SYNC_YANDEX_CALENDAR,
                        )
                    ),
                    Job.status == JOB_STATUS_FAILED,
                    Job.run_after <= now,
                )
            )
        )
        for job in failed_jobs:
            self._queue.rearm_failed_recurring_job(
                job,
                settings.source_sync_failed_rearm_seconds,
            )
