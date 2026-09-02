import imaplib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.connectors.yandex.constants import DEFAULT_MAIL_FOLDER
from app.connectors.yandex.errors import YandexImapError


@dataclass(frozen=True)
class YandexMailHistoryUidPage:
    uids: list[int]
    next_before_uid: int | None
    complete: bool


def normalize_history_search_uids(
    search_data: bytes | str | None,
    before_uid: int,
) -> list[int]:
    if not search_data:
        return []
    if isinstance(search_data, bytes):
        search_data = search_data.decode("ascii", errors="replace")
    unique: set[int] = set()
    for token in search_data.split():
        try:
            uid = int(token)
        except ValueError as exc:
            raise YandexImapError("malformed imap uid search response") from exc
        if uid <= 0:
            continue
        if uid >= before_uid:
            continue
        unique.add(uid)
    return sorted(unique)


def history_uids_page_from_search(
    search_data: bytes | str | None,
    before_uid: int,
    max_results: int,
) -> YandexMailHistoryUidPage:
    if max_results <= 0:
        raise ValueError("max_results must be positive")
    if before_uid <= 1:
        return YandexMailHistoryUidPage(uids=[], next_before_uid=None, complete=True)

    uids = normalize_history_search_uids(search_data, before_uid)
    if not uids:
        return YandexMailHistoryUidPage(uids=[], next_before_uid=None, complete=True)

    if len(uids) <= max_results:
        return YandexMailHistoryUidPage(uids=uids, next_before_uid=None, complete=True)

    page_uids = uids[-max_results:]
    return YandexMailHistoryUidPage(
        uids=page_uids,
        next_before_uid=page_uids[0],
        complete=False,
    )


def read_uidvalidity_from_response(imap: imaplib.IMAP4_SSL) -> int:
    try:
        response = imap.response("UIDVALIDITY")
    except imaplib.IMAP4.error as exc:
        raise YandexImapError("failed to read imap UIDVALIDITY") from exc
    if response is None:
        raise YandexImapError("imap UIDVALIDITY response missing")
    try:
        response_code, data = response
    except (TypeError, ValueError) as exc:
        raise YandexImapError("imap UIDVALIDITY response malformed") from exc
    if response_code != "UIDVALIDITY":
        raise YandexImapError("imap UIDVALIDITY response missing")
    if not data or data[0] is None:
        raise YandexImapError("imap UIDVALIDITY response missing")
    raw = data[0]
    if isinstance(raw, bytes):
        raw = raw.decode("ascii", errors="replace")
    value = str(raw).strip()
    if not value.isdigit() or int(value) <= 0:
        raise YandexImapError("imap UIDVALIDITY response malformed")
    return int(value)


def incremental_uids_from_search_result(
    search_data: bytes | str | None,
    after_uid: int,
    max_results: int,
) -> list[int]:
    if not search_data:
        return []
    if isinstance(search_data, bytes):
        search_data = search_data.decode("ascii", errors="replace")
    uids = sorted(int(uid) for uid in search_data.split() if int(uid) > after_uid)
    if len(uids) > max_results:
        return uids[:max_results]
    return uids


class ImapTransport(Protocol):
    def select_folder(self, folder: str) -> int:
        ...

    def search_uids_initial(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
    ) -> list[int]:
        ...

    def search_uids_incremental(
        self,
        folder: str,
        after_uid: int,
        max_results: int,
    ) -> list[int]:
        ...

    def search_uids_history_page(
        self,
        folder: str,
        since_date: datetime,
        before_date: datetime,
        before_uid: int,
        max_results: int,
    ) -> YandexMailHistoryUidPage:
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
        self._selected_folder: str | None = None
        self._uidvalidity: int | None = None

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
            self._selected_folder = None
            self._uidvalidity = None

    def select_folder(self, folder: str) -> int:
        imap = self._connect()
        if self._selected_folder != folder:
            try:
                status, _ = imap.select(folder, readonly=True)
            except imaplib.IMAP4.error as exc:
                raise YandexImapError(f"failed to select imap folder {folder}") from exc
            if status != "OK":
                raise YandexImapError(f"failed to select imap folder {folder}")
            self._uidvalidity = read_uidvalidity_from_response(imap)
            self._selected_folder = folder
        if self._uidvalidity is None:
            raise YandexImapError("imap UIDVALIDITY unavailable")
        return self._uidvalidity

    def search_uids_initial(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
    ) -> list[int]:
        self.select_folder(folder)
        imap = self._connect()
        date_str = since_date.strftime("%d-%b-%Y")
        criteria = f"(SINCE {date_str})"
        try:
            status, data = imap.uid("search", None, criteria)
        except imaplib.IMAP4.error as exc:
            raise YandexImapError("failed to search imap messages") from exc
        if status != "OK" or not data or not data[0]:
            return []
        uids = sorted(int(uid) for uid in data[0].split())
        if len(uids) > max_results:
            return uids[-max_results:]
        return uids

    def search_uids_incremental(
        self,
        folder: str,
        after_uid: int,
        max_results: int,
    ) -> list[int]:
        self.select_folder(folder)
        imap = self._connect()
        criteria = f"(UID {after_uid + 1}:*)"
        try:
            status, data = imap.uid("search", None, criteria)
        except imaplib.IMAP4.error as exc:
            raise YandexImapError("failed to search imap messages") from exc
        if status != "OK" or not data or not data[0]:
            return []
        return incremental_uids_from_search_result(data[0], after_uid, max_results)

    def search_uids_history_page(
        self,
        folder: str,
        since_date: datetime,
        before_date: datetime,
        before_uid: int,
        max_results: int,
    ) -> YandexMailHistoryUidPage:
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        if before_uid <= 1:
            return YandexMailHistoryUidPage(uids=[], next_before_uid=None, complete=True)

        self.select_folder(folder)
        imap = self._connect()
        since_str = since_date.strftime("%d-%b-%Y")
        before_str = before_date.strftime("%d-%b-%Y")
        uid_upper = before_uid - 1
        criteria = f"(SINCE {since_str}) (BEFORE {before_str}) (UID 1:{uid_upper})"
        try:
            status, data = imap.uid("search", None, criteria)
        except imaplib.IMAP4.error as exc:
            raise YandexImapError("failed to search imap messages") from exc
        if status != "OK" or not data or not data[0]:
            return YandexMailHistoryUidPage(uids=[], next_before_uid=None, complete=True)
        return history_uids_page_from_search(data[0], before_uid, max_results)

    def fetch_message(self, folder: str, uid: int) -> bytes:
        self.select_folder(folder)
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


class FakeImapTransport:
    def __init__(
        self,
        uidvalidity: int = 1,
        messages: dict[int, bytes] | None = None,
        folder: str = DEFAULT_MAIL_FOLDER,
        tx_checker: object | None = None,
        history_matching_uids: list[int] | None = None,
    ) -> None:
        self._uidvalidity = uidvalidity
        self._messages = messages or {}
        self._folder = folder
        self.fetch_calls: list[int] = []
        self.history_search_calls: list[dict[str, object]] = []
        self.initial_search_calls: list[dict[str, object]] = []
        self.incremental_search_calls: list[dict[str, object]] = []
        self._tx_checker = tx_checker
        self._history_matching_uids = history_matching_uids

    def _history_candidates(self, before_uid: int) -> list[int]:
        if self._history_matching_uids is not None:
            source = self._history_matching_uids
        else:
            source = sorted(self._messages.keys())
        return sorted(uid for uid in source if uid < before_uid)

    def _check_tx(self) -> None:
        if self._tx_checker is not None:
            assert not self._tx_checker()

    def select_folder(self, folder: str) -> int:
        self._check_tx()
        if folder != self._folder:
            raise YandexImapError(f"failed to select imap folder {folder}")
        return self._uidvalidity

    def search_uids_initial(
        self,
        folder: str,
        since_date: datetime,
        max_results: int,
    ) -> list[int]:
        self._check_tx()
        self.initial_search_calls.append(
            {"folder": folder, "since_date": since_date, "max_results": max_results}
        )
        uids = sorted(self._messages.keys())
        if len(uids) > max_results:
            return uids[-max_results:]
        return uids

    def search_uids_incremental(
        self,
        folder: str,
        after_uid: int,
        max_results: int,
    ) -> list[int]:
        self._check_tx()
        self.incremental_search_calls.append(
            {"folder": folder, "after_uid": after_uid, "max_results": max_results}
        )
        uids = sorted(uid for uid in self._messages if uid > after_uid)
        if len(uids) > max_results:
            return uids[:max_results]
        return uids

    def search_uids_history_page(
        self,
        folder: str,
        since_date: datetime,
        before_date: datetime,
        before_uid: int,
        max_results: int,
    ) -> YandexMailHistoryUidPage:
        self._check_tx()
        if before_uid <= 1:
            return YandexMailHistoryUidPage(uids=[], next_before_uid=None, complete=True)
        self.history_search_calls.append(
            {
                "folder": folder,
                "since_date": since_date,
                "before_date": before_date,
                "before_uid": before_uid,
                "max_results": max_results,
            }
        )
        candidates = self._history_candidates(before_uid)
        payload = b" ".join(str(uid).encode() for uid in candidates)
        return history_uids_page_from_search(payload, before_uid, max_results)

    def fetch_message(self, folder: str, uid: int) -> bytes:
        self._check_tx()
        self.fetch_calls.append(uid)
        if uid not in self._messages:
            raise YandexImapError(f"failed to fetch imap message uid {uid}")
        return self._messages[uid]
