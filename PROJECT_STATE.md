# Project state

## Current phase

PHASE 17 — Yandex Calendar (final corrective applied; awaiting code review)

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync
  - Separate encrypted Calendar app password (`yandex_calendar_accounts`, migration `0012`)
  - Principal discovery → calendar-home-set → calendars
  - Bounded query with recurrence expand; sync-collection Depth 0 + RFC6578 DAV:limit wrapper
  - Incremental sync-collection with calendar-data expand in same 60d-back / 90d-forward window
  - Sync-token persisted only after full CalDAV resource batch applied (occurrence budget gates next fetch)
  - Deletion tombstones all user-scoped occurrences sharing `metadata.event_href`
  - No DB transaction leak before CalDAV network calls (noop deletions commit)
  - Merged 200 propstats (etag + calendar-data split across propstats)
  - Initial query deterministic cap when >100 resources; incremental raises on untruncated overflow
  - TZID/all-day parsing; occurrence external_id includes RECURRENCE-ID
  - Offline tests: `tests/test_yandex_calendar.py` (231 suite green)

## Not done

- PHASE 17 deploy / live CalDAV smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 acceptance.
