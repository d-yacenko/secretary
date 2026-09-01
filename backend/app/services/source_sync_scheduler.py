from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import (
    CALENDAR_READONLY_SCOPE,
    DRIVE_READONLY_SCOPE,
    GMAIL_READONLY_SCOPE,
)
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.mattermost.credentials import MattermostAccountStore
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.core.config import settings
from app.db.models import (
    GoogleAccount,
    Job,
    MattermostAccount,
    YandexCalendarAccount,
    YandexMailAccount,
)
from app.jobs.constants import (
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_DRIVE,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
    JOB_TYPE_SYNC_MATTERMOST,
    JOB_TYPE_SYNC_YANDEX_CALENDAR,
    JOB_TYPE_SYNC_YANDEX_MAIL,
    RECURRING_SOURCE_JOB_TYPES,
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
        self._maintain_mattermost_accounts(
            MattermostAccountStore(self._session, encryption)
        )
        self._retire_stale_recurring_jobs(encryption)
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
            if DRIVE_READONLY_SCOPE in scopes and self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_GOOGLE_DRIVE, account.id
            ):
                triggered.append(f"google_drive:{account.id}")
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
        mattermost_store = MattermostAccountStore(self._session, encryption)
        for account in mattermost_store.list_accounts(user_id):
            if self._queue.trigger_recurring_source_job(
                user_id, JOB_TYPE_SYNC_MATTERMOST, account.id
            ):
                triggered.append(f"mattermost:{account.id}")
        return triggered

    def _maintain_google_accounts(self, _store: GoogleAccountStore) -> None:
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
            if DRIVE_READONLY_SCOPE in scopes:
                self._queue.ensure_recurring_source_job(
                    JOB_TYPE_SYNC_GOOGLE_DRIVE,
                    account.id,
                    user_id,
                )

    def _maintain_yandex_mail_accounts(self, _store: YandexMailAccountStore) -> None:
        accounts = list(self._session.scalars(select(YandexMailAccount)))
        for account in accounts:
            self._queue.ensure_recurring_source_job(
                JOB_TYPE_SYNC_YANDEX_MAIL,
                account.id,
                account.user_id,
            )

    def _maintain_yandex_calendar_accounts(self, _store: YandexCalendarAccountStore) -> None:
        accounts = list(self._session.scalars(select(YandexCalendarAccount)))
        for account in accounts:
            self._queue.ensure_recurring_source_job(
                JOB_TYPE_SYNC_YANDEX_CALENDAR,
                account.id,
                account.user_id,
            )

    def _maintain_mattermost_accounts(self, _store: MattermostAccountStore) -> None:
        accounts = list(self._session.scalars(select(MattermostAccount)))
        for account in accounts:
            self._queue.ensure_recurring_source_job(
                JOB_TYPE_SYNC_MATTERMOST,
                account.id,
                account.user_id,
            )

    def _collect_expected_recurring_jobs(
        self,
        encryption: CredentialEncryption,
    ) -> set[tuple[str, UUID, UUID]]:
        expected: set[tuple[str, UUID, UUID]] = set()
        for account in self._session.scalars(select(GoogleAccount)):
            scopes = set(account.scopes or [])
            if GMAIL_READONLY_SCOPE in scopes:
                expected.add(
                    (JOB_TYPE_SYNC_GOOGLE_GMAIL, account.id, account.user_id)
                )
            if CALENDAR_READONLY_SCOPE in scopes:
                expected.add(
                    (JOB_TYPE_SYNC_GOOGLE_CALENDAR, account.id, account.user_id)
                )
            if DRIVE_READONLY_SCOPE in scopes:
                expected.add(
                    (JOB_TYPE_SYNC_GOOGLE_DRIVE, account.id, account.user_id)
                )
        for account in self._session.scalars(select(YandexMailAccount)):
            expected.add((JOB_TYPE_SYNC_YANDEX_MAIL, account.id, account.user_id))
        for account in self._session.scalars(select(YandexCalendarAccount)):
            expected.add(
                (JOB_TYPE_SYNC_YANDEX_CALENDAR, account.id, account.user_id)
            )
        for account in self._session.scalars(select(MattermostAccount)):
            expected.add((JOB_TYPE_SYNC_MATTERMOST, account.id, account.user_id))
        return expected

    def _retire_stale_recurring_jobs(self, encryption: CredentialEncryption) -> None:
        expected = self._collect_expected_recurring_jobs(encryption)
        jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.type.in_(tuple(RECURRING_SOURCE_JOB_TYPES)),
                    Job.status.in_(
                        (
                            JOB_STATUS_PENDING,
                            JOB_STATUS_RUNNING,
                            JOB_STATUS_FAILED,
                        )
                    ),
                )
            )
        )
        for job in jobs:
            raw_account_id = (job.payload or {}).get("account_id")
            if not raw_account_id:
                self._queue.retire_recurring_source_job(job)
                continue
            account_id = UUID(str(raw_account_id))
            key = (job.type, account_id, job.user_id)
            if key not in expected:
                self._queue.retire_recurring_source_job(job)

    def _rearm_failed_recurring_jobs(self) -> None:
        now = utcnow()
        failed_jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.type.in_(
                        (
                            JOB_TYPE_SYNC_GOOGLE_GMAIL,
                            JOB_TYPE_SYNC_GOOGLE_CALENDAR,
                            JOB_TYPE_SYNC_GOOGLE_DRIVE,
                            JOB_TYPE_SYNC_YANDEX_MAIL,
                            JOB_TYPE_SYNC_YANDEX_CALENDAR,
                            JOB_TYPE_SYNC_MATTERMOST,
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
