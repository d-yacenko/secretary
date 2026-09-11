from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.temporal_hint import (
    DATE_KIND_ABSOLUTE,
    DATE_KIND_RELATIVE_DAY,
    END_KIND_ABSOLUTE,
    END_KIND_DURATION_MINUTES,
    END_KIND_LOCAL_TIME,
    END_PRECISION_EXACT,
    END_PRECISION_UNKNOWN,
)
from app.services.temporal_signals_constants import (
    TEMPORAL_SIGNAL_HORIZON_DAYS,
    TEMPORAL_SIGNAL_MAX_DURATION,
    TEMPORAL_SIGNAL_MIN_DURATION,
)
from app.services.temporal_signals_models import ParsedExactSignal, ResolvedTemporalSignal

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def aware_instant(value: datetime) -> datetime | None:
    if value.tzinfo is None:
        return None
    return value


def load_timezone(name: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def source_reference_timestamp(occurred_at: datetime | None, metadata: dict) -> datetime | None:
    if occurred_at is not None:
        return aware_instant(occurred_at)
    raw = metadata.get("timestamp")
    if isinstance(raw, datetime):
        return aware_instant(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw.strip())
        except ValueError:
            return None
        return aware_instant(parsed)
    return None


def _combine_local(tz: ZoneInfo, day, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def _parse_absolute_date(value: str):
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_naive_local(value: str) -> datetime | None:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def resolve_weekday_date(anchor: datetime, weekday: str) -> datetime:
    tz = anchor.tzinfo
    assert tz is not None
    target_wd = _WEEKDAY_INDEX[weekday]
    anchor_date = anchor.date()
    delta = (target_wd - anchor_date.weekday()) % 7
    return anchor_date + timedelta(days=delta)


def resolve_exact_signal(
    parsed: ParsedExactSignal,
    *,
    timezone_name: str,
    source_reference_at: datetime | None,
) -> tuple[ResolvedTemporalSignal | None, str | None]:
    tz = load_timezone(timezone_name)
    if tz is None:
        return None, "invalid_timezone"
    if parsed.date_kind != DATE_KIND_ABSOLUTE and source_reference_at is None:
        return None, "missing_source_reference"
    if source_reference_at is not None and source_reference_at.tzinfo is None:
        return None, "naive_source_reference"

    anchor = source_reference_at.astimezone(tz) if source_reference_at is not None else None
    if parsed.date_kind == DATE_KIND_ABSOLUTE:
        day = _parse_absolute_date(parsed.absolute_date or "")
        if day is None:
            return None, "invalid_absolute_date"
    elif parsed.date_kind == DATE_KIND_RELATIVE_DAY:
        assert anchor is not None
        day = anchor.date() + timedelta(days=int(parsed.relative_day_offset or 0))
    else:
        assert anchor is not None
        day = resolve_weekday_date(anchor, parsed.weekday or "")
        start_candidate = _combine_local(tz, day, parsed.start_hour, parsed.start_minute)
        if start_candidate <= anchor:
            day = day + timedelta(days=7)

    start_at = _combine_local(tz, day, parsed.start_hour, parsed.start_minute)
    due_at = None
    if parsed.end_precision == END_PRECISION_EXACT:
        if parsed.end_kind == END_KIND_DURATION_MINUTES:
            minutes = parsed.end_duration_minutes
            if minutes is None:
                return None, "invalid_duration"
            due_at = start_at + timedelta(minutes=minutes)
        elif parsed.end_kind == END_KIND_LOCAL_TIME:
            if parsed.end_hour is None or parsed.end_minute is None:
                return None, "invalid_end_time"
            due_at = _combine_local(tz, day, parsed.end_hour, parsed.end_minute)
            if due_at <= start_at:
                due_at = due_at + timedelta(days=1)
        elif parsed.end_kind == END_KIND_ABSOLUTE:
            naive = _parse_naive_local(parsed.end_absolute or "")
            if naive is None:
                return None, "invalid_end_absolute"
            due_at = naive.replace(tzinfo=tz)
        else:
            return None, "invalid_end_kind"
        if due_at <= start_at:
            return None, "end_not_after_start"
        duration = due_at - start_at
        if duration < TEMPORAL_SIGNAL_MIN_DURATION or duration > TEMPORAL_SIGNAL_MAX_DURATION:
            return None, "impossible_duration"

    if source_reference_at is not None:
        if start_at < source_reference_at:
            return None, "start_in_the_past"
        horizon = source_reference_at + timedelta(days=TEMPORAL_SIGNAL_HORIZON_DAYS)
        if start_at > horizon:
            return None, "beyond_horizon"

    reference = source_reference_at if source_reference_at is not None else start_at
    return (
        ResolvedTemporalSignal(
            title=parsed.concise_title,
            start_at=start_at,
            due_at=due_at,
            end_precision=parsed.end_precision if due_at is not None else END_PRECISION_UNKNOWN,
            participation=parsed.participation,
            extraction_confidence=parsed.extraction_confidence,
            semantic_subject=parsed.semantic_subject,
            source_reference_at=reference,
        ),
        None,
    )
