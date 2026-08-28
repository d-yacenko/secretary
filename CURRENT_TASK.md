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

## Live repair verification (post-multiget deploy)

| Metric | Before | After |
|--------|--------|-------|
| yandex_calendar objects | 44 | 44 |
| recurrence_id occurrences | 4 | 4 |
| RRULE masters (no recurrence_id) | 2 | 2 |
| UID `141zhhu5wu91aiyjysevnpohyandex.ru` occurrences | 4 | 4 |

### Repair sync (forced reconciliation, sync_token removed)

| Field | Value |
|-------|-------|
| synchronized | 47 |
| created | 0 |
| updated | 0 |
| unchanged | 47 |
| tombstoned | 0 |
| jobs_enqueued | 0 |

### Following steady-state sync

All counters 0.

### Yandex multiget+expand probe

- Recurring resource `141zhhu5wu91aiyjysevnpohyandex.ru.ics`: HTTP 207, 14 VEVENT, 13 RECURRENCE-ID
- RRULE master `141zhhu5wm72gbs2cx4rgcphyandex.ru.ics`: HTTP 207, 1 VEVENT (Yandex returns master only for this series)

Repair upserted existing objects without duplicates; series already materialized via prior sync-collection path.

### Token state (present/absent only)

Both calendars: `sync_token` present, `backfill_cursor` absent (unchanged after repair).

### Other checks

- Ownership: 44 bootstrap, 0 other users
- embed_object jobs: 44 done
- `/health`: ok
- API/worker logs: no credentials

