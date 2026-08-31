"""Trusted source navigation targets for objects."""

from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Object
from app.local.constants import PROVIDER_LOCAL_DEVICE
from app.services.errors import NotFoundError

_SAFE_WEB_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class OpenTarget:
    available: bool
    action: str
    label: str
    url: str | None = None
    device_key: str | None = None
    local_path: str | None = None
    reason: str | None = None


class OpenTargetService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    def resolve(self, object_id: UUID) -> OpenTarget:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", object_id)

        provider = (obj.provider or "").lower()
        meta = obj.metadata_ or {}

        if provider == "gmail" and obj.kind == "email":
            return self._gmail_target(obj, meta)
        if provider in {"yandex_mail", "yandex"} and obj.kind == "email":
            return self._yandex_mail_target(obj, meta)
        if provider in {"google_calendar", "google"} and obj.kind in {"event", "calendar_event"}:
            return self._calendar_target(obj, meta)
        if obj.kind == "web_page":
            return self._web_target(obj)
        if provider == PROVIDER_LOCAL_DEVICE:
            return self._local_device_target(obj, meta)
        if obj.kind == "file" and provider in {"gmail", "yandex_mail"}:
            return self._attachment_target(obj, meta)
        if obj.canonical_uri and self._is_safe_web_url(obj.canonical_uri):
            return OpenTarget(
                available=True,
                action="web_url",
                label="Открыть страницу",
                url=obj.canonical_uri,
            )
        return OpenTarget(
            available=False,
            action="unavailable",
            label="Открыть в источнике",
            reason="no_trusted_open_target",
        )

    def _gmail_target(self, obj: Object, meta: dict) -> OpenTarget:
        thread_id = meta.get("thread_id")
        if thread_id:
            url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
            return OpenTarget(
                available=True,
                action="web_url",
                label="Открыть в Gmail",
                url=url,
            )
        message_id = meta.get("message_id")
        if message_id:
            url = f"https://mail.google.com/mail/u/0/#all/{message_id}"
            return OpenTarget(
                available=True,
                action="web_url",
                label="Открыть в Gmail",
                url=url,
            )
        return OpenTarget(
            available=True,
            action="web_url",
            label="Открыть в Gmail",
            url="https://mail.google.com/mail/u/0/#inbox",
        )

    def _yandex_mail_target(self, obj: Object, meta: dict) -> OpenTarget:
        # Yandex IMAP sync does not provide a reliable per-message browser URL.
        return OpenTarget(
            available=True,
            action="web_url",
            label="Открыть Яндекс.Почту",
            url="https://mail.yandex.ru/",
            reason="yandex_exact_message_link_unavailable",
        )

    def _calendar_target(self, obj: Object, meta: dict) -> OpenTarget:
        html_link = meta.get("html_link") or obj.canonical_uri
        if html_link and self._is_safe_web_url(html_link):
            return OpenTarget(
                available=True,
                action="web_url",
                label="Открыть в календаре",
                url=html_link,
            )
        return OpenTarget(
            available=False,
            action="unavailable",
            label="Открыть в источнике",
            reason="calendar_link_missing",
        )

    def _web_target(self, obj: Object) -> OpenTarget:
        uri = obj.canonical_uri
        if uri and self._is_safe_web_url(uri):
            return OpenTarget(
                available=True,
                action="web_url",
                label="Открыть страницу",
                url=uri,
            )
        return OpenTarget(
            available=False,
            action="unavailable",
            label="Открыть в источнике",
            reason="unsafe_or_missing_web_uri",
        )

    def _local_device_target(self, obj: Object, meta: dict) -> OpenTarget:
        device_key = meta.get("device_key")
        local_path = (
            meta.get("client_source_path")
            or meta.get("local_relative_path")
            or meta.get("local_source_path")
        )
        if obj.kind == "folder":
            folder_path = meta.get("local_root_path") or local_path
            if device_key and folder_path:
                return OpenTarget(
                    available=True,
                    action="local_folder",
                    label="Открыть папку",
                    device_key=str(device_key),
                    local_path=str(folder_path),
                )
        if device_key and local_path:
            return OpenTarget(
                available=True,
                action="local_file",
                label="Открыть файл",
                device_key=str(device_key),
                local_path=str(local_path),
            )
        return OpenTarget(
            available=False,
            action="unavailable",
            label="Открыть файл",
            reason="local_path_missing",
        )

    def _attachment_target(self, obj: Object, meta: dict) -> OpenTarget:
        parent_id = meta.get("parent_email_id")
        if parent_id:
            parent = self._session.scalar(
                select(Object).where(
                    Object.id == UUID(str(parent_id)),
                    Object.user_id == self._user_id,
                )
            )
            if parent is not None:
                return self.resolve(parent.id)
        return OpenTarget(
            available=False,
            action="unavailable",
            label="Открыть в источнике",
            reason="attachment_parent_missing",
        )

    @staticmethod
    def _is_safe_web_url(url: str) -> bool:
        parsed = urlparse(url.strip())
        if parsed.scheme not in _SAFE_WEB_SCHEMES:
            return False
        if parsed.username or parsed.password:
            return False
        return bool(parsed.netloc)
