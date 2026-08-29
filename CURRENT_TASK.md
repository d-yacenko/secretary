# Current task — PHASE 21 (awaiting final acceptance)

## Status

PHASE 20 accepted / closed. Manual Linux smoke completed by user.

PHASE 21 architecture accepted (74f15a3). Final corrective implemented:

- Accept ValidationError → HTTP 422
- Today terminal tasks filtered in SQL before limit
- `GET /today` returns `day_start`; overdue uses instant comparison
- Inbox/Today/ObjectDetail dispose-safe async guards

PHASE 22 not started.

## Verification

```bash
cd backend && pytest && ruff check .
cd client && flutter analyze && flutter test && flutter build apk --debug
```

## STOP

Awaiting PHASE 21 final acceptance. Do not start PHASE 22.
