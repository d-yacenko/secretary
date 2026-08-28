# Current task — PHASE 17 deploy + live smoke

## Status

Deploy complete (`17fd823` on VDS). Migration `0012` applied. Health OK. Data preserved.

**STOP** — awaiting Yandex Calendar connection from operator, then first/second sync smoke.

## Deploy verification (done)

- `/health` → ok
- `api` + `worker` + `db` up
- Alembic `0012 (head)`
- Bootstrap user `00000000-0000-4000-8000-000000000001`
- Gmail 50, Yandex Mail 50 objects preserved
- `yandex_calendar_accounts`: 0 rows (not connected)

## Next (after operator confirms connect)

1. First `POST /connectors/yandex/calendar/sync`
2. Second sync
3. Live-smoke report

## Defer

- PHASE 18
