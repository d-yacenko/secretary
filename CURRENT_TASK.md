# Current task — Universal Intake Iteration A-R2 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1: **implemented and deployed**.

Universal Intake Iteration A-R1-R1 corrective: **implemented and deployed**.

Universal Intake Iteration A-R2 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

## Iteration A-R2 scope (implemented)

Product semantics correction per explicit user feedback:

- Global «+» / Capture = **task capture only** (reference UX: `1562db7a7764e387ce4c9518a7032b801fcf0cdf`)
- Removed universal Capture: Note/Task selector, note/link submit branches, `prepareForGenericAdd()`, `CaptureMode`, exact-URL link routing in Capture
- Inbox intake bar = canonical explicit incoming-object intake (note, link, file, folder, voice)
- Deterministic Inbox dispatch: exact `http`/`https` URL → `POST /intake/link`; other text → `POST /capture/note`
- Inbox microphone feeds same input field; no auto-submit
- Inbox section: «Последние входящие»; `recent_source_objects` API field unchanged
- `InboxSourceObjectOut.origin` in API + Flutter; truthful origin for «Спросить секретаря»
- Backend A/R1/R1-R1 web intake preserved; no new migration (Alembic `0026`)

## Deploy

Application SHA: `057627ae6a0c610b1a801ea2798a293ef1453c5c`

Deployed VDS SHA: `057627ae6a0c610b1a801ea2798a293ef1453c5c` (clean)

Architect encrypted context commit: `427e2e835b1a3a329c3c95a1bb0ce0fe595728b2`

Encrypted context blob SHA: `99cb601b147a3e2d2b49c1fc0eab7cd9d9db7f0f`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

## Next

STOP — await architect review before user manual E2E. Do not start format parity B or Safe External Actions.
