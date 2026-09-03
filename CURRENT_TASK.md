# Current task — Universal Intake Iteration A-R1 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake & Format Parity — Iteration A: **implemented**, **awaiting architect review and manual E2E** (not accepted).

Universal Intake Iteration A-R1 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

## Iteration A-R1 scope (implemented)

- Redirect idempotency: `external_id` = normalized requested URL; `canonical_uri` / `final_url` track fetched destination
- Full extracted web text to bounded representations (no pre-chunk 8K cut)
- Stale embedding / semantic-summary invalidation on web content revision change
- Binary magic-byte detection when Content-Type missing or wrong
- Quick Add defaults to Note after successful submit; task context forces Task mode (exact URL does not override)
- Contract regressions: `query_objects` note/web_page, Inbox provider fairness, Flutter inbox presentation tests

## Deploy

Application SHA: `1e873dbd902ac53a8123328e05e2201d55df6dc8`

Deployed VDS SHA: `1e873dbd902ac53a8123328e05e2201d55df6dc8` (clean)

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production smoke: existing note retrieve PASS, existing web_page retrieve PASS, Google/Yandex provider detection unchanged

## Next

STOP — await architect review before user manual E2E. Do not start format parity B or Safe External Actions.
