from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.mattermost.credentials import MattermostAccountStore
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.core.config import settings
from app.db.models import Job
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_SYNC_GOOGLE_CALENDAR,
    JOB_TYPE_SYNC_GOOGLE_GMAIL,
    JOB_TYPE_SYNC_MATTERMOST,
    JOB_TYPE_SYNC_YANDEX_CALENDAR,
    JOB_TYPE_SYNC_YANDEX_MAIL,
    RECURRING_SOURCE_JOB_TYPES,
)
from app.services.job_queue_service import utcnow
from app.services.source_sync_preference_service import SourceSyncPreferenceService

SOURCE_TYPE_LABELS = {
    JOB_TYPE_SYNC_GOOGLE_GMAIL: ("gmail", "Gmail"),
    JOB_TYPE_SYNC_GOOGLE_CALENDAR: ("google_calendar", "Google Calendar"),
    JOB_TYPE_SYNC_YANDEX_MAIL: ("yandex_mail", "Yandex Mail"),
    JOB_TYPE_SYNC_YANDEX_CALENDAR: ("yandex_calendar", "Yandex Calendar"),
    JOB_TYPE_SYNC_MATTERMOST: ("mattermost", "Mattermost"),
}

_STATUS_PRIORITY = {
    JOB_STATUS_RUNNING: 0,
    JOB_STATUS_PENDING: 1,
    JOB_STATUS_FAILED: 2,
    JOB_STATUS_DONE: 3,
}


@dataclass(frozen=True)
class SourceStatusRow:
    source: str
    provider: str
    account_id: UUID
    account_label: str
    enabled: bool
    status: str
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    next_sync_at: datetime | None
    last_error: str | None


class SourceStatusService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._preferences = SourceSyncPreferenceService.build(session)

    def list_status(self) -> list[SourceStatusRow]:
        jobs = list(
            self._session.scalars(
                select(Job).where(
                    Job.user_id == self._user_id,
                    Job.type.in_(tuple(RECURRING_SOURCE_JOB_TYPES)),
                )
            )
        )
        grouped: dict[tuple[str, UUID], list[Job]] = {}
        for job in jobs:
            raw_account_id = (job.payload or {}).get("account_id")
            if not raw_account_id:
                continue
            account_id = UUID(str(raw_account_id))
            grouped.setdefault((job.type, account_id), []).append(job)

        account_labels = self._account_label_map()
        rows: list[SourceStatusRow] = []
        for (job_type, account_id), job_group in grouped.items():
            job = self._pick_status_job(job_group)
            if job is None:
                continue
            source_key, _label = SOURCE_TYPE_LABELS.get(job_type, (job_type, job_type))
            effective = self._preferences.get_effective_preference(self._user_id, source_key)
            payload = job.payload or {}
            last_success_raw = payload.get("last_success_at")
            last_success_at = None
            if isinstance(last_success_raw, str):
                try:
                    last_success_at = datetime.fromisoformat(last_success_raw)
                except ValueError:
                    last_success_at = None
            last_attempt_at = job.locked_at or (
                job.updated_at if job.attempts > 0 else None
            )
            if not effective.enabled:
                rows.append(
                    SourceStatusRow(
                        source=source_key,
                        provider=source_key,
                        account_id=account_id,
                        account_label=account_labels.get(account_id, str(account_id)),
                        enabled=False,
                        status="disabled",
                        last_success_at=last_success_at,
                        last_attempt_at=last_attempt_at,
                        next_sync_at=None,
                        last_error=None,
                    )
                )
                continue
            rows.append(
                SourceStatusRow(
                    source=source_key,
                    provider=source_key,
                    account_id=account_id,
                    account_label=account_labels.get(account_id, str(account_id)),
                    enabled=True,
                    status=self._derive_status(job),
                    last_success_at=last_success_at,
                    last_attempt_at=last_attempt_at,
                    next_sync_at=(
                        job.run_after if job.status == JOB_STATUS_PENDING else None
                    ),
                    last_error=job.last_error,
                )
            )
        rows.sort(key=lambda row: (row.provider, row.account_label))
        return rows

    @staticmethod
    def _pick_status_job(jobs: list[Job]) -> Job | None:
        if not jobs:
            return None
        return min(
            jobs,
            key=lambda job: (
                _STATUS_PRIORITY.get(job.status, 99),
                -(job.updated_at.timestamp()),
            ),
        )

    def _derive_status(self, job: Job) -> str:
        if job.status == JOB_STATUS_RUNNING:
            return "syncing"
        if job.status == JOB_STATUS_FAILED:
            return "error"
        if job.last_error:
            return "error"
        now = utcnow()
        if job.status == JOB_STATUS_PENDING and job.run_after > now:
            return "scheduled"
        return "pending"

    def _account_label_map(self) -> dict[UUID, str]:
        if not settings.secretary_credential_key:
            return {}
        encryption = CredentialEncryption(settings.secretary_credential_key)
        labels: dict[UUID, str] = {}
        google_store = GoogleAccountStore(self._session, encryption)
        for account in google_store.list_accounts(self._user_id):
            labels[account.id] = account.email
        yandex_mail_store = YandexMailAccountStore(self._session, encryption)
        for account in yandex_mail_store.list_accounts(self._user_id):
            labels[account.id] = account.email
        yandex_calendar_store = YandexCalendarAccountStore(self._session, encryption)
        for account in yandex_calendar_store.list_accounts(self._user_id):
            labels[account.id] = account.email
        mattermost_store = MattermostAccountStore(self._session, encryption)
        for account in mattermost_store.list_accounts(self._user_id):
            labels[account.id] = self._mattermost_account_label(account)
        return labels

    @staticmethod
    def _mattermost_account_label(account) -> str:
        display_name = (account.display_name or "").strip()
        username = (account.username or "").strip()
        server = (account.server_url or "").strip()
        if display_name and server:
            return f"{display_name} @ {server}"
        if username and server:
            return f"{username} @ {server}"
        if display_name:
            return display_name
        if username:
            return username
        return server or str(account.id)
