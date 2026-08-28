# Current task — PHASE 17 (implemented; awaiting review)

## Status

PHASE 17 code complete. Offline tests pass. Not deployed; no live CalDAV smoke.

## Goal

Synchronize Yandex Calendar via read-only CalDAV into user-scoped `event` objects.

## Implemented

- `yandex_calendar_accounts` + migration `0012` (separate Calendar app password)
- `POST /connectors/yandex/calendar/connect`, `POST /connectors/yandex/calendar/sync`
- CalDAV discover → bounded query or sync-collection incremental
- Objects: `kind=event`, `provider=yandex_calendar`
- Tests: `tests/test_yandex_calendar.py`

## Defer

- Calendar write.
- Deploy / live smoke until code review acceptance.

## Roadmap note

PHASE 19.5 — Secretary Authentication & Connections must land before PHASE 20 Flutter.

## Note

Stop for review. Do not auto-start PHASE 18.
