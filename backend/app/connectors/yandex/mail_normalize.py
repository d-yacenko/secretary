import re
from datetime import datetime, timezone
from email import message_from_bytes
from email.utils import getaddresses, parsedate_to_datetime, parseaddr
from typing import Any

from app.connectors.yandex.constants import DEFAULT_MAIL_FOLDER, MAX_EMAIL_BODY_CHARS


def _strip_html(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", without_tags).strip()


def _parse_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [addr for _, addr in getaddresses([value]) if addr]


def _compact_headers(msg: Any) -> dict[str, str]:
    keep = ("message-id", "in-reply-to", "references", "reply-to", "list-id")
    compact: dict[str, str] = {}
    for name in keep:
        value = msg.get(name)
        if value:
            compact[name] = str(value)
    return compact


def _extract_body(msg: Any) -> str | None:
    if msg.is_multipart():
        plain: str | None = None
        html_body: str | None = None
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            content_type = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
            except TypeError:
                payload = None
            if not payload:
                continue
            decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            if content_type == "text/plain" and plain is None:
                plain = decoded.strip()
            elif content_type == "text/html" and html_body is None:
                html_body = decoded
        if plain:
            return plain
        if html_body:
            return _strip_html(html_body)
        return None

    try:
        payload = msg.get_payload(decode=True)
    except TypeError:
        payload = None
    if not payload:
        return None
    decoded = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    if msg.get_content_type() == "text/html":
        return _strip_html(decoded)
    return decoded.strip()


def _parse_timestamp(msg: Any) -> datetime:
    date_header = msg.get("Date")
    if not date_header:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(date_header)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def build_external_id(folder: str, uidvalidity: int, uid: int) -> str:
    return f"{folder.lower()}:{uidvalidity}:{uid}"


def normalize_imap_message(
    raw_bytes: bytes,
    folder: str,
    uid: int,
    uidvalidity: int,
) -> dict[str, Any]:
    msg = message_from_bytes(raw_bytes)
    subject = msg.get("Subject")
    sender = msg.get("From")
    recipients = _parse_addresses(msg.get("To"))
    cc = _parse_addresses(msg.get("Cc"))
    timestamp = _parse_timestamp(msg)
    body_text = _extract_body(msg)
    message_id_header = msg.get("Message-ID")

    metadata = {
        "folder": folder,
        "imap_uid": uid,
        "imap_uidvalidity": uidvalidity,
        "message_id": str(message_id_header) if message_id_header else None,
        "sender": sender,
        "recipients": recipients,
        "cc": cc,
        "subject": subject,
        "timestamp": timestamp.isoformat(),
        "headers": _compact_headers(msg),
    }

    body = body_text[:MAX_EMAIL_BODY_CHARS] if body_text else None
    external_id = build_external_id(folder, uidvalidity, uid)

    return {
        "external_id": external_id,
        "kind": "email",
        "provider": "yandex_mail",
        "origin": "source",
        "state": "observed",
        "title": str(subject) if subject else f"Yandex message {external_id}",
        "body": body,
        "metadata": metadata,
    }
