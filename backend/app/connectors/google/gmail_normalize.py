import base64
import html
import re
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any

from app.connectors.google.constants import GMAIL_READONLY_SCOPE


def _header_value(headers: list[dict[str, Any]], name: str) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            value = header.get("value")
            return str(value) if value is not None else None
    return None


def _parse_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in value.split(",")]
    addresses: list[str] = []
    for part in parts:
        _, addr = parseaddr(part)
        if addr:
            addresses.append(addr)
    return addresses


def _decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return raw.decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    collapsed = re.sub(r"\s+", " ", without_tags)
    return html.unescape(collapsed).strip()


def _extract_body(payload: dict[str, Any]) -> str | None:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if data and mime_type == "text/plain":
        return _decode_body_data(str(data)).strip()

    parts = payload.get("parts", [])
    plain: str | None = None
    html_body: str | None = None
    for part in parts:
        part_type = part.get("mimeType", "")
        part_body = part.get("body", {})
        part_data = part_body.get("data")
        if not part_data:
            nested = _extract_body(part)
            if nested and part_type == "text/plain":
                plain = nested
            elif nested and part_type == "text/html" and html_body is None:
                html_body = nested
            continue
        decoded = _decode_body_data(str(part_data))
        if part_type == "text/plain" and plain is None:
            plain = decoded.strip()
        elif part_type == "text/html" and html_body is None:
            html_body = decoded

    if plain:
        return plain
    if html_body:
        return _strip_html(html_body)
    return None


def _compact_headers(headers: list[dict[str, Any]]) -> dict[str, str]:
    keep = ("message-id", "in-reply-to", "references", "reply-to", "list-id")
    compact: dict[str, str] = {}
    for header in headers:
        name = str(header.get("name", "")).lower()
        if name in keep and header.get("value"):
            compact[name] = str(header["value"])
    return compact


def normalize_gmail_message(message: dict[str, Any]) -> dict[str, Any]:
    message_id = str(message.get("id", ""))
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    internal_ms = message.get("internalDate")
    if internal_ms is not None:
        timestamp = datetime.fromtimestamp(int(internal_ms) / 1000, tz=timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)

    subject = _header_value(headers, "Subject")
    sender = _header_value(headers, "From")
    recipients = _parse_addresses(_header_value(headers, "To"))
    cc = _parse_addresses(_header_value(headers, "Cc"))
    body_text = _extract_body(payload)
    labels = [str(label) for label in message.get("labelIds", [])]

    metadata = {
        "message_id": message_id,
        "thread_id": str(message.get("threadId", "")),
        "sender": sender,
        "recipients": recipients,
        "cc": cc,
        "subject": subject,
        "timestamp": timestamp.isoformat(),
        "headers": _compact_headers(headers),
        "labels": labels,
    }
    if body_text:
        metadata["body_text"] = body_text[:8000]

    return {
        "external_id": message_id,
        "kind": "email",
        "provider": "gmail",
        "origin": "source",
        "state": "observed",
        "title": subject or f"Gmail message {message_id}",
        "metadata": metadata,
        "scopes": [GMAIL_READONLY_SCOPE],
    }
