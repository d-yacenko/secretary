# Project state

## Current phase

PHASE 17 — Yandex Calendar (last correctness fix applied; awaiting code review)

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync
  - Separate encrypted Calendar app password (`yandex_calendar_accounts`, migration `0012`)
  - Resumable bounded backfill with baseline `pending_sync_token` (T1) before steady-state
  - Adaptive time-slice splitting for dense backfill slices (no href cursor pagination)
  - Future horizon reconciliation (`covered_window_end`)
  - Incremental recurring reconcile for all changed resources (including single VEVENT)
  - Stale sync-token detection via `valid-sync-token` precondition only
  - Search excludes `status=deleted` by default
  - Offline tests: 246 suite green

## Not done

- PHASE 17 deploy / live CalDAV smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 acceptance.
