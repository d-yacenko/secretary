from datetime import datetime, timezone
from typing import Any

from app.connectors.yandex.constants import MAX_EVENT_BODY_CHARS


def _parse_ical_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 8 and raw.isdigit():
        return datetime.fromisoformat(f"{raw}T00:00:00+00:00")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _unfold_ical_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_vevent_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in _unfold_ical_lines(block):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        name = key.split(";", 1)[0].upper()
        if name in {"UID", "SUMMARY", "DESCRIPTION", "DTSTART", "DTEND", "LOCATION", "STATUS", "LAST-MODIFIED"}:
            fields[name] = value.strip()
    return fields


def extract_vevent_blocks(ical_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_event = False
    for line in ical_text.splitlines():
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            in_event = True
            current = [line]
            continue
        if in_event:
            current.append(line)
            if upper.startswith("END:VEVENT"):
                blocks.append("\n".join(current))
                in_event = False
    return blocks


def build_external_id(calendar_href: str, event_uid: str) -> str:
    calendar_key = calendar_href.rstrip("/")
    return f"{calendar_key}:{event_uid}"


def normalize_caldav_event(
    ical_text: str,
    calendar_href: str,
    calendar_summary: str | None = None,
    etag: str | None = None,
    event_href: str | None = None,
) -> dict[str, Any] | None:
    blocks = extract_vevent_blocks(ical_text)
    if not blocks:
        return None
    fields = _parse_vevent_block(blocks[0])
    event_uid = fields.get("UID")
    if not event_uid:
        return None

    start_at = _parse_ical_datetime(fields.get("DTSTART", ""))
    end_at = _parse_ical_datetime(fields.get("DTEND", ""))
    description = fields.get("DESCRIPTION")
    body = None
    if description:
        body = description[:MAX_EVENT_BODY_CHARS]

    title = fields.get("SUMMARY") or f"Calendar event {event_uid}"
    calendar_key = calendar_href.rstrip("/")

    metadata: dict[str, Any] = {
        "calendar_href": calendar_href,
        "calendar_id": calendar_key,
        "event_uid": event_uid,
        "calendar_summary": calendar_summary,
        "event_href": event_href,
        "etag": etag,
        "status": fields.get("STATUS"),
        "location": fields.get("LOCATION"),
        "last_modified": fields.get("LAST-MODIFIED"),
    }

    return {
        "external_id": build_external_id(calendar_href, event_uid),
        "kind": "event",
        "provider": "yandex_calendar",
        "origin": "source",
        "state": "observed",
        "title": title,
        "body": body,
        "start_at": start_at,
        "due_at": end_at,
        "metadata": metadata,
    }
