from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.google.constants import CALENDAR_READONLY_SCOPE, GMAIL_READONLY_SCOPE
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.encryption import CredentialEncryption
from app.connectors.yandex.calendar_credentials import YandexCalendarAccountStore
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.core.config import settings


@dataclass(frozen=True)
class GoogleConnectionStatus:
    connected: bool
    email: str | None = None
    gmail_available: bool = False
    calendar_available: bool = False


@dataclass(frozen=True)
class YandexMailConnectionStatus:
    connected: bool
    email: str | None = None


@dataclass(frozen=True)
class YandexCalendarConnectionStatus:
    connected: bool
    email: str | None = None


@dataclass(frozen=True)
class ConnectionStatusSnapshot:
    google: GoogleConnectionStatus
    yandex_mail: YandexMailConnectionStatus
    yandex_calendar: YandexCalendarConnectionStatus


class ConnectionStatusService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def snapshot(self) -> ConnectionStatusSnapshot:
        google = self._google_status()
        yandex_mail = self._yandex_mail_status()
        yandex_calendar = self._yandex_calendar_status()
        return ConnectionStatusSnapshot(
            google=google,
            yandex_mail=yandex_mail,
            yandex_calendar=yandex_calendar,
        )

    def _google_status(self) -> GoogleConnectionStatus:
        if not settings.secretary_credential_key:
            return GoogleConnectionStatus(connected=False)
        encryption = CredentialEncryption(settings.secretary_credential_key)
        store = GoogleAccountStore(self._session, encryption)
        accounts = store.list_accounts(self._user_id)
        if not accounts:
            return GoogleConnectionStatus(connected=False)
        account = accounts[0]
        scopes = set(account.scopes or [])
        return GoogleConnectionStatus(
            connected=True,
            email=account.email,
            gmail_available=GMAIL_READONLY_SCOPE in scopes,
            calendar_available=CALENDAR_READONLY_SCOPE in scopes,
        )

    def _yandex_mail_status(self) -> YandexMailConnectionStatus:
        if not settings.secretary_credential_key:
            return YandexMailConnectionStatus(connected=False)
        encryption = CredentialEncryption(settings.secretary_credential_key)
        store = YandexMailAccountStore(self._session, encryption)
        accounts = store.list_accounts(self._user_id)
        if not accounts:
            return YandexMailConnectionStatus(connected=False)
        return YandexMailConnectionStatus(connected=True, email=accounts[0].email)

    def _yandex_calendar_status(self) -> YandexCalendarConnectionStatus:
        if not settings.secretary_credential_key:
            return YandexCalendarConnectionStatus(connected=False)
        encryption = CredentialEncryption(settings.secretary_credential_key)
        store = YandexCalendarAccountStore(self._session, encryption)
        accounts = store.list_accounts(self._user_id)
        if not accounts:
            return YandexCalendarConnectionStatus(connected=False)
        return YandexCalendarConnectionStatus(connected=True, email=accounts[0].email)
