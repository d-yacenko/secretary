"""Google Calendar bounded history backfill state on GoogleAccount.calendar_sync_state."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

HISTORY_BACKFILL_KEY = "history_backfill"
HISTORY_BACKFILL_VERSION = 1
CALENDARS_KEY = "calendars"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CalendarHistoryActiveWindow:
    active_start: datetime
    active_end: datetime
    next_page_token: str | None


@dataclass(frozen=True)
class CalendarHistoryBackfillPlan:
    window: CalendarHistoryActiveWindow | None
    calendar_backfill: dict[str, Any]


def empty_calendar_sync_state() -> dict[str, Any]:
    return {}


def get_history_backfill(state: dict[str, Any]) -> dict[str, Any]:
    backfill = state.get(HISTORY_BACKFILL_KEY)
    if not isinstance(backfill, dict):
        return {}
    return dict(backfill)


def set_history_backfill(state: dict[str, Any], backfill: dict[str, Any]) -> dict[str, Any]:
    updated = dict(state)
    if backfill:
        updated[HISTORY_BACKFILL_KEY] = backfill
    else:
        updated.pop(HISTORY_BACKFILL_KEY, None)
    return updated


def get_calendar_backfill(backfill: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    calendars = backfill.get(CALENDARS_KEY)
    if not isinstance(calendars, dict):
        return {}
    entry = calendars.get(calendar_id)
    if not isinstance(entry, dict):
        return {}
    return sanitize_calendar_backfill(dict(entry))


def set_calendar_backfill(
    backfill: dict[str, Any],
    calendar_id: str,
    calendar_entry: dict[str, Any],
) -> dict[str, Any]:
    backfill = dict(backfill)
    calendars = dict(backfill.get(CALENDARS_KEY) or {})
    if calendar_entry is not None:
        calendars[calendar_id] = sanitize_calendar_backfill(calendar_entry)
    else:
        calendars.pop(calendar_id, None)
    if calendars:
        backfill[CALENDARS_KEY] = calendars
    else:
        backfill.pop(CALENDARS_KEY, None)
    backfill["version"] = HISTORY_BACKFILL_VERSION
    return backfill


def desired_history_window(history_days: int) -> tuple[datetime, datetime]:
    desired_end = utcnow()
    desired_start = desired_end - timedelta(days=history_days)
    return desired_start, desired_end


def format_stored_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_stored_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_optional_datetime(entry: dict[str, Any], key: str) -> datetime | None:
    raw = entry.get(key)
    if raw is None:
        return None
    try:
        return parse_stored_datetime(str(raw))
    except (ValueError, TypeError):
        return None


def sanitize_calendar_backfill(entry: dict[str, Any]) -> dict[str, Any]:
    entry = dict(entry)
    active_start = _parse_optional_datetime(entry, "active_start")
    active_end = _parse_optional_datetime(entry, "active_end")
    scanned_start = _parse_optional_datetime(entry, "scanned_start")
    scanned_end = _parse_optional_datetime(entry, "scanned_end")

    if active_start is None or active_end is None or active_start >= active_end:
        entry.pop("active_start", None)
        entry.pop("active_end", None)
        entry.pop("next_page_token", None)
    else:
        entry["active_start"] = format_stored_datetime(active_start)
        entry["active_end"] = format_stored_datetime(active_end)

    if (
        scanned_start is not None
        and scanned_end is not None
        and scanned_start < scanned_end
    ):
        entry["scanned_start"] = format_stored_datetime(scanned_start)
        entry["scanned_end"] = format_stored_datetime(scanned_end)
    else:
        entry.pop("scanned_start", None)
        entry.pop("scanned_end", None)

    token = entry.get("next_page_token")
    if token is not None and not str(token):
        entry.pop("next_page_token", None)

    return entry


def continue_active_window(calendar_backfill: dict[str, Any]) -> CalendarHistoryActiveWindow | None:
    calendar_backfill = sanitize_calendar_backfill(calendar_backfill)
    active_start = _parse_optional_datetime(calendar_backfill, "active_start")
    active_end = _parse_optional_datetime(calendar_backfill, "active_end")
    if active_start is None or active_end is None or active_start >= active_end:
        return None
    token = calendar_backfill.get("next_page_token")
    return CalendarHistoryActiveWindow(
        active_start=active_start,
        active_end=active_end,
        next_page_token=str(token) if token else None,
    )


def _active_window_within_desired(
    active_start: datetime,
    active_end: datetime,
    desired_start: datetime,
    desired_end: datetime,
) -> bool:
    return (
        active_start < active_end
        and active_start >= desired_start
        and active_end <= desired_end
    )


def clear_active_window(calendar_backfill: dict[str, Any]) -> dict[str, Any]:
    calendar_backfill = dict(calendar_backfill)
    calendar_backfill.pop("active_start", None)
    calendar_backfill.pop("active_end", None)
    calendar_backfill.pop("next_page_token", None)
    return calendar_backfill


def reconcile_active_window(
    calendar_backfill: dict[str, Any],
    history_days: int,
) -> dict[str, Any]:
    calendar_backfill = sanitize_calendar_backfill(calendar_backfill)
    continuing = continue_active_window(calendar_backfill)
    if continuing is None:
        return calendar_backfill
    desired_start, desired_end = desired_history_window(history_days)
    if _active_window_within_desired(
        continuing.active_start,
        continuing.active_end,
        desired_start,
        desired_end,
    ):
        return calendar_backfill
    return clear_active_window(calendar_backfill)


def plan_history_active_window(
    calendar_backfill: dict[str, Any],
    history_days: int,
) -> CalendarHistoryBackfillPlan:
    calendar_backfill = reconcile_active_window(calendar_backfill, history_days)
    continuing = continue_active_window(calendar_backfill)
    if continuing is not None:
        return CalendarHistoryBackfillPlan(window=continuing, calendar_backfill=calendar_backfill)

    desired_start, desired_end = desired_history_window(history_days)
    scanned_start = _parse_optional_datetime(calendar_backfill, "scanned_start")
    scanned_end = _parse_optional_datetime(calendar_backfill, "scanned_end")

    if scanned_start is None and scanned_end is None:
        if desired_start >= desired_end:
            return CalendarHistoryBackfillPlan(window=None, calendar_backfill=calendar_backfill)
        return CalendarHistoryBackfillPlan(
            window=CalendarHistoryActiveWindow(
                active_start=desired_start,
                active_end=desired_end,
                next_page_token=None,
            ),
            calendar_backfill=calendar_backfill,
        )

    if scanned_start is not None and desired_start < scanned_start:
        return CalendarHistoryBackfillPlan(
            window=CalendarHistoryActiveWindow(
                active_start=desired_start,
                active_end=scanned_start,
                next_page_token=None,
            ),
            calendar_backfill=calendar_backfill,
        )

    if scanned_end is not None and scanned_end < desired_end:
        return CalendarHistoryBackfillPlan(
            window=CalendarHistoryActiveWindow(
                active_start=scanned_end,
                active_end=desired_end,
                next_page_token=None,
            ),
            calendar_backfill=calendar_backfill,
        )

    return CalendarHistoryBackfillPlan(window=None, calendar_backfill=calendar_backfill)


def complete_active_window(calendar_backfill: dict[str, Any]) -> dict[str, Any]:
    calendar_backfill = sanitize_calendar_backfill(calendar_backfill)
    active_start = _parse_optional_datetime(calendar_backfill, "active_start")
    active_end = _parse_optional_datetime(calendar_backfill, "active_end")
    if active_start is None or active_end is None:
        return clear_active_window(calendar_backfill)

    scanned_start = _parse_optional_datetime(calendar_backfill, "scanned_start")
    scanned_end = _parse_optional_datetime(calendar_backfill, "scanned_end")

    if scanned_start is None and scanned_end is None:
        calendar_backfill["scanned_start"] = format_stored_datetime(active_start)
        calendar_backfill["scanned_end"] = format_stored_datetime(active_end)
    elif scanned_end is not None and active_start == scanned_end:
        calendar_backfill["scanned_end"] = format_stored_datetime(active_end)
    elif scanned_start is not None and active_end == scanned_start:
        calendar_backfill["scanned_start"] = format_stored_datetime(active_start)
    else:
        return clear_active_window(calendar_backfill)

    return clear_active_window(calendar_backfill)


def persist_active_page_token(
    calendar_backfill: dict[str, Any],
    window: CalendarHistoryActiveWindow,
    next_page_token: str | None,
) -> dict[str, Any]:
    calendar_backfill = dict(calendar_backfill)
    calendar_backfill["active_start"] = format_stored_datetime(window.active_start)
    calendar_backfill["active_end"] = format_stored_datetime(window.active_end)
    if next_page_token:
        calendar_backfill["next_page_token"] = next_page_token
    else:
        calendar_backfill.pop("next_page_token", None)
    return calendar_backfill


def start_active_window(
    calendar_backfill: dict[str, Any],
    window: CalendarHistoryActiveWindow,
) -> dict[str, Any]:
    calendar_backfill = dict(calendar_backfill)
    calendar_backfill["active_start"] = format_stored_datetime(window.active_start)
    calendar_backfill["active_end"] = format_stored_datetime(window.active_end)
    calendar_backfill.pop("next_page_token", None)
    return calendar_backfill


def plan_calendar_history(
    state: dict[str, Any],
    calendar_id: str,
    history_days: int,
) -> tuple[CalendarHistoryBackfillPlan, dict[str, Any]]:
    backfill = get_history_backfill(state)
    calendar_backfill = get_calendar_backfill(backfill, calendar_id)
    plan = plan_history_active_window(calendar_backfill, history_days)
    entry: dict[str, Any] | None = plan.calendar_backfill
    if plan.window is not None and not entry:
        entry = {}
    updated_backfill = set_calendar_backfill(backfill, calendar_id, entry)
    updated_state = set_history_backfill(state, updated_backfill)
    return plan, updated_state
