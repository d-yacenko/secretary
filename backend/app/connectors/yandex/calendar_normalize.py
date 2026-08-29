from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.connectors.yandex.constants import MAX_EVENT_BODY_CHARS


def _unfold_ical_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_ical_property(line: str) -> tuple[str, dict[str, str], str] | None:
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    parts = key.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            param_name, param_value = part.split("=", 1)
            params[param_name.upper()] = param_value
    return name, params, value.strip()


def _parse_ical_datetime_value(value: str, params: dict[str, str]) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if params.get("VALUE") == "DATE" or (len(raw) == 8 and raw.isdigit()):
        return datetime.fromisoformat(f"{raw}T00:00:00+00:00")
    tzid = params.get("TZID")
    if tzid:
        try:
            zone = ZoneInfo(tzid)
        except (KeyError, ValueError):
            return None
        raw = raw.removesuffix("Z")
        if "T" in raw:
            date_part, time_part = raw.split("T", 1)
            year = int(date_part[0:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            hour = int(time_part[0:2])
            minute = int(time_part[2:4])
            second = int(time_part[4:6]) if len(time_part) >= 6 else 0
            local = datetime(year, month, day, hour, minute, second, tzinfo=zone)
            return local.astimezone(UTC)
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_vevent_block(block: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    property_params: dict[str, dict[str, str]] = {}
    for line in _unfold_ical_lines(block):
        parsed = _parse_ical_property(line)
        if parsed is None:
            continue
        name, params, value = parsed
        if name in {
            "UID",
            "SUMMARY",
            "DESCRIPTION",
            "DTSTART",
            "DTEND",
            "LOCATION",
            "STATUS",
            "LAST-MODIFIED",
            "RECURRENCE-ID",
            "RRULE",
        }:
            fields[name] = value
            property_params[name] = params
    return {"fields": fields, "params": property_params}


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


def build_occurrence_identity(event_uid: str, recurrence_id: str | None) -> str:
    if recurrence_id:
        return f"{event_uid}@{recurrence_id}"
    return event_uid


def build_external_id(
    calendar_href: str,
    event_uid: str,
    recurrence_id: str | None = None,
) -> str:
    calendar_key = calendar_href.rstrip("/")
    identity = build_occurrence_identity(event_uid, recurrence_id)
    return f"{calendar_key}:{identity}"


def normalize_caldav_events(
    ical_text: str,
    calendar_href: str,
    calendar_summary: str | None = None,
    etag: str | None = None,
    event_href: str | None = None,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
) -> list[dict[str, Any]]:
    normalized_events: list[dict[str, Any]] = []
    for block in extract_vevent_blocks(ical_text):
        parsed = _parse_vevent_block(block)
        fields = parsed["fields"]
        params = parsed["params"]
        event_uid = fields.get("UID")
        if not event_uid:
            continue

        recurrence_id = fields.get("RECURRENCE-ID")
        start_at = _parse_ical_datetime_value(fields.get("DTSTART", ""), params.get("DTSTART", {}))
        end_at = _parse_ical_datetime_value(fields.get("DTEND", ""), params.get("DTEND", {}))
        if (
            time_min is not None
            and time_max is not None
            and start_at is not None
            and (start_at < time_min or start_at > time_max)
        ):
            continue

        description = fields.get("DESCRIPTION")
        body = description[:MAX_EVENT_BODY_CHARS] if description else None
        title = fields.get("SUMMARY") or f"Calendar event {event_uid}"

        metadata: dict[str, Any] = {
            "calendar_href": calendar_href,
            "calendar_id": calendar_href.rstrip("/"),
            "event_uid": event_uid,
            "calendar_summary": calendar_summary,
            "event_href": event_href,
            "etag": etag,
            "status": fields.get("STATUS"),
            "location": fields.get("LOCATION"),
            "last_modified": fields.get("LAST-MODIFIED"),
            "recurrence_id": recurrence_id,
            "rrule": fields.get("RRULE"),
        }

        normalized_events.append(
            {
                "external_id": build_external_id(calendar_href, event_uid, recurrence_id),
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
        )
    return normalized_events


def normalize_caldav_event(
    ical_text: str,
    calendar_href: str,
    calendar_summary: str | None = None,
    etag: str | None = None,
    event_href: str | None = None,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
) -> dict[str, Any] | None:
    events = normalize_caldav_events(
        ical_text,
        calendar_href=calendar_href,
        calendar_summary=calendar_summary,
        etag=etag,
        event_href=event_href,
        time_min=time_min,
        time_max=time_max,
    )
    if not events:
        return None
    return events[0]
