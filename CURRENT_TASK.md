# Current task — PHASE 21 (awaiting final acceptance)

## Status

PHASE 20 accepted / closed. Manual Linux smoke completed by user.

PHASE 21 architecture accepted (74f15a3). Final corrective implemented (78aaa28):

- Accept ValidationError → HTTP 422
- Today terminal tasks filtered in SQL before limit
- `GET /today` returns `day_start`; overdue uses `due_at < day_start`
- Inbox/Today/ObjectDetail dispose-safe async guards

VDS manual smoke (PHASE 21 client): Inbox, Accept/Ignore, Today sections OK.

PHASE 22 not started.

## VDS deployment (2026-08-29)

- SHA: `78aaa28`
- Alembic: `0015 (head)`
- Live checks: `/health` 200, `/notifications?status=unresolved` 200, `/today` 200

## Verification

```bash
cd backend && pytest && ruff check .
cd client && flutter analyze && flutter test && flutter build apk --debug
```

## STOP

Awaiting PHASE 21 final acceptance. Do not start PHASE 22.
