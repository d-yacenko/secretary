import imaplib
from datetime import datetime, timezone
from typing import Protocol

from app.connectors.yandex.constants import DEFAULT_MAIL_FOLDER
from app.connectors.yandex.errors import YandexImapError


class ImapTransport(Protocol):
    def list_recent_uids(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
        min_uid: int | None,
    ) -> tuple[int, list[int]]:
        ...

    def fetch_message(self, folder: str, uid: int) -> bytes:
        ...


class ImaplibTransport:
    def __init__(self, host: str, port: int, email: str, password: str) -> None:
        self._host = host
        self._port = port
        self._email = email
        self._password = password
        self._imap: imaplib.IMAP4_SSL | None = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        if self._imap is None:
            try:
                imap = imaplib.IMAP4_SSL(self._host, self._port)
                imap.login(self._email, self._password)
            except imaplib.IMAP4.error as exc:
                raise YandexImapError("failed to connect to yandex imap") from exc
            self._imap = imap
        return self._imap

    def close(self) -> None:
        if self._imap is not None:
            try:
                self._imap.logout()
            except imaplib.IMAP4.error:
                pass
            self._imap = None

    def list_recent_uids(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
        min_uid: int | None,
    ) -> tuple[int, list[int]]:
        imap = self._connect()
        try:
            status, select_data = imap.select(folder, readonly=True)
        except imaplib.IMAP4.error as exc:
            raise YandexImapError(f"failed to select imap folder {folder}") from exc
        if status != "OK":
            raise YandexImapError(f"failed to select imap folder {folder}")

        uidvalidity = self._parse_uidvalidity(select_data)
        date_str = since_date.strftime("%d-%b-%Y")
        criteria = f"(SINCE {date_str})"
        if min_uid is not None and min_uid > 0:
            criteria = f"(UID {min_uid + 1}:* SINCE {date_str})"

        try:
            status, data = imap.uid("search", None, criteria)
        except imaplib.IMAP4.error as exc:
            raise YandexImapError("failed to search imap messages") from exc
        if status != "OK" or not data or not data[0]:
            return uidvalidity, []

        uids = sorted(int(uid) for uid in data[0].split())
        if len(uids) > max_results:
            uids = uids[-max_results:]
        return uidvalidity, uids

    def fetch_message(self, folder: str, uid: int) -> bytes:
        imap = self._connect()
        try:
            status, data = imap.uid("fetch", str(uid), "(RFC822)")
        except imaplib.IMAP4.error as exc:
            raise YandexImapError(f"failed to fetch imap message uid {uid}") from exc
        if status != "OK" or not data or data[0] is None:
            raise YandexImapError(f"failed to fetch imap message uid {uid}")

        part = data[0]
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
            return part[1]
        raise YandexImapError(f"failed to fetch imap message uid {uid}")

    def _parse_uidvalidity(self, select_data: list) -> int:
        if not select_data:
            return 0
        response = select_data[0]
        if isinstance(response, bytes):
            response = response.decode("ascii", errors="replace")
        if isinstance(response, str) and "[UIDVALIDITY" in response:
            start = response.index("[UIDVALIDITY") + len("[UIDVALIDITY ")
            end = response.index("]", start)
            return int(response[start:end].strip())
        return 0


class FakeImapTransport:
    def __init__(
        self,
        uidvalidity: int = 1,
        messages: dict[int, bytes] | None = None,
        folder: str = DEFAULT_MAIL_FOLDER,
    ) -> None:
        self._uidvalidity = uidvalidity
        self._messages = messages or {}
        self._folder = folder
        self.fetch_calls: list[int] = []

    def list_recent_uids(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
        min_uid: int | None,
    ) -> tuple[int, list[int]]:
        if folder != self._folder:
            return self._uidvalidity, []
        uids = sorted(self._messages.keys())
        if min_uid is not None:
            uids = [uid for uid in uids if uid > min_uid]
        if len(uids) > max_results:
            uids = uids[-max_results:]
        return self._uidvalidity, uids

    def fetch_message(self, folder: str, uid: int) -> bytes:
        self.fetch_calls.append(uid)
        if uid not in self._messages:
            raise YandexImapError(f"failed to fetch imap message uid {uid}")
        return self._messages[uid]
