# Project state

## Current phase

PHASE 17 — Yandex Calendar (corrective applied; awaiting code review)

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync
  - Separate encrypted Calendar app password (`yandex_calendar_accounts`, migration `0012`)
  - Principal discovery → calendar-home-set → calendars
  - Bounded query with recurrence expand; sync-collection Depth 0 + partial tokens
  - Deletion tombstones via `status=deleted` + `metadata.caldav_deleted`
  - TZID/all-day parsing; occurrence external_id includes RECURRENCE-ID
  - Offline tests: `tests/test_yandex_calendar.py`

## Not done

- PHASE 17 deploy / live CalDAV smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 acceptance.
