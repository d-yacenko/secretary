# Current task — PHASE 21 (awaiting review)

## Status

PHASE 20 accepted / closed. Manual Linux smoke completed by user.

PHASE 21 implemented: Inbox, Today, Object Detail, task-proposal Accept, manual capture context wiring.

PHASE 22 not started.

## Verification

```bash
cd backend && pytest && ruff check .
cd client && flutter analyze && flutter test && flutter build apk --debug
```

## STOP

Awaiting PHASE 21 review. Do not start PHASE 22.
