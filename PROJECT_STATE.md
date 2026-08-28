# Project state

## Current phase

PHASE 17 — Yandex Calendar (data-correctness corrective applied; awaiting code review)

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync
  - Separate encrypted Calendar app password (`yandex_calendar_accounts`, migration `0012`)
  - Principal discovery → calendar-home-set → calendars
  - Resumable bounded backfill before steady-state sync-token; slice cursor + href cursor
  - Future horizon reconciliation for newly-entering events (`covered_window_end`)
  - Incremental recurring reconcile tombstones removed expanded occurrences
  - Stale sync-token recovery via bounded backfill, then fresh token
  - RFC6578 DAV:limit; sync-token safety; multi-occurrence tombstones; merged propstats
  - Search excludes `status=deleted` by default; direct get-by-id still returns tombstones
  - Offline tests: `tests/test_yandex_calendar.py`, `tests/test_search.py` (237 suite green)

## Not done

- PHASE 17 deploy / live CalDAV smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 acceptance.
