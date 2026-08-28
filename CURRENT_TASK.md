# Current task — PHASE 17

## Status

**live-smoked, awaiting final acceptance** (recurrence corrective applied)

## Recurrence corrective

Yandex rejects `c:expand` in `calendar-query`. Bounded backfill/reconciliation now uses:
1. **Step A:** `calendar-query` (href + etag, no expand, closed `c:filter`)
2. **Step B:** `calendar-multiget` with `calendar-data/expand` in bounded batches

Live probe: Yandex accepts multiget+expand (207, 14 VEVENT blocks on recurring resource).

Incremental `sync-collection` expand unchanged.

## Live smoke (prior)

- Account `ydv@arenadata.io`, 2 calendars, 44 objects after initial backfill
- First backfill sync: created 44, unchanged 3, synchronized 47, jobs_enqueued 44
- Second steady-state sync: all counters 0
- Ownership, embed jobs, health, credentials: OK

## Defer

- PHASE 18
