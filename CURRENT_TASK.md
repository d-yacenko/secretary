# Current task — Universal Intake Iteration A deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake & Format Parity — Iteration A (Quick Capture + generic web links): **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

## Iteration A scope (implemented)

- `POST /capture/note` — user-authored notes (`kind=note`, no task lifecycle)
- Generic public web URLs via existing `POST /intake/link` (`provider=web`, `kind=web_page`)
- Bounded `web_fetch` reuse with binary/metadata-only path
- Inbox recent feed includes `note` and `web_page` (tasks excluded)
- Universal Flutter «Добавить» capture (note default, explicit task mode, exact-URL link intake)
- Voice fills text field only (no auto-submit)

## Deploy

Application SHA: `476de0e989944bbadbf7858aa0e6633c490a1999`

Deployed VDS SHA: `476de0e989944bbadbf7858aa0e6633c490a1999` (clean)

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production smoke: note retrieve PASS, web_page retrieve PASS, URL idempotency PASS, open-target PASS, Google/Yandex provider detection PASS

## Next

STOP — await architect review and manual user E2E. Format parity (DOC/XLS/PPT/ODT/…) is next iteration, not Safe External Actions.
