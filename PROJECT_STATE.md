# Project state

## Current phase

PHASE 17 — Yandex Calendar (implemented; awaiting code review)

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases, including live Yandex Mail)
- PHASE 17: Yandex Calendar CalDAV sync
  - `yandex_calendar_accounts` + migration `0012`
  - Separate encrypted **Calendar** app password (not Mail password)
  - `POST /connectors/yandex/calendar/connect`, `POST /connectors/yandex/calendar/sync`
  - Read-only CalDAV: discover calendars, bounded time-range query, sync-token incremental
  - Objects: `kind=event`, `provider=yandex_calendar` (same shape as Google Calendar)
  - Bounded ~60d back / 90d forward / max 100 events / 10 calendars
  - Offline tests: `tests/test_yandex_calendar.py`

## Not done

- PHASE 17 deploy / live CalDAV smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 acceptance (do not start without user go-ahead).
