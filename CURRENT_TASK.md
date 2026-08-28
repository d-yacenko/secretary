# Current task — PHASE 17

## Status

**live-smoked, awaiting final acceptance**

Live smoke completed on VDS `185.233.107.66` (account `db6353cb-1ac6-4478-9f7f-5fd9f31867de`).

## Connection

- Email: `ydv@arenadata.io`
- CalDAV host: `caldav.yandex.ru`
- Account ID: `db6353cb-1ac6-4478-9f7f-5fd9f31867de`

## First sync counters (primary backfill)

| Field | Value |
|-------|-------|
| synchronized | 47 |
| created | 44 |
| updated | 0 |
| unchanged | 3 |
| tombstoned | 0 |
| jobs_enqueued | 44 |

## Second sync counters (steady state)

| Field | Value |
|-------|-------|
| synchronized | 0 |
| created | 0 |
| updated | 0 |
| unchanged | 0 |
| tombstoned | 0 |
| jobs_enqueued | 0 |

## Discovered calendars (2)

| Name | Href suffix | Objects imported |
|------|-------------|------------------|
| Мои события | `events-18154946/` | 44 |
| Не забыть | `todos-7121590/` | 0 |

## yandex_calendar objects

- Total: **44**

## Ownership

- Bootstrap user `00000000-0000-4000-8000-000000000001`: **44**
- Other users: **0**

## Recurring occurrences

- Objects with `recurrence_id`: **4**
- Objects with `rrule` (master): **2**
- UID `141zhhu5wu91aiyjysevnpohyandex.ru` → **4** distinct occurrences (not collapsed)
- Example recurrence_ids: `20260728T143000`, `20260818T143000`, `20260825T143000`, `20260901T143000`

## Timezone / all-day

- Timed events store correct UTC offsets (e.g. `2026-07-02 09:30:00+00` … `10:30:00+00`)
- RRULE masters present with weekly rules (`BYDAY=TH,FR`, `BYDAY=MO`)
- All-day events (`start_at` at `00:00:00 UTC`): **0** in imported window

## embed_object jobs

- Status `done`: **44**
- Objects with embedding: **44**

## /health

- `{"status":"ok"}`

## Credential / log checks

- API responses: no app password or encrypted credentials
- API logs: clean (no credential patterns)
- Worker logs: clean (no credential patterns)
- Sync-token values not exposed in API or logs

## Backfill / sync state (present/absent/changed only — no token values)

| Calendar | sync_token | pending_sync_token | backfill_cursor | covered_window_end |
|----------|------------|--------------------|-----------------|---------------------|
| Мои события | present | absent | absent | present |
| Не забыть | present | absent | absent | present |

- Backfill: **complete** (both calendars)
- Sync-token on second sync: **unchanged** (steady state)

## CalDAV hotfix (included in this commit)

Yandex CalDAV rejects `c:expand` in `calendar-query` (HTTP 400) and requires closing `</c:filter>` in query XML. Fix in `caldav_transport.py`; expand for recurring remains via `sync-collection`.

## Defer

- PHASE 18
