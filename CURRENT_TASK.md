# Current task — PHASE 17 data-correctness corrective (awaiting review)

## Status

PHASE 17 data-correctness corrective applied. Full offline suite: 237 passed, 2 skipped. Not deployed.

## Data-correctness scope

- Resumable bounded backfill before steady-state sync-token establishment
- Future horizon reconciliation (`covered_window_end`) without full-window rescan
- Incremental recurring resource reconcile tombstones removed occurrences
- Stale sync-token recovery via bounded backfill
- Search excludes deleted objects by default

## Defer

- Deploy / live CalDAV smoke until acceptance
- Calendar app password request
- PHASE 18

## Note

STOP for review.
