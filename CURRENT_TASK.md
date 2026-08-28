# Current task — PHASE 17 last correctness fix (awaiting review)

## Status

PHASE 17 last correctness fix applied. Full offline suite: 246 passed, 2 skipped. Not deployed.

## Last fix scope

- Baseline `pending_sync_token` captured at backfill start, never replaced by later discovery
- Adaptive time-slice splitting for dense backfill (no href cursor over truncated query)
- Incremental reconcile tombstones for all changed resources (including single VEVENT)
- Stale sync-token only on `valid-sync-token` precondition; ordinary 403/409 surface as errors

## Defer

- Deploy / live CalDAV smoke until acceptance
- Calendar app password request
- PHASE 18

## Note

STOP for review.
