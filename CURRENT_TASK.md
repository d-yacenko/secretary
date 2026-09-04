# Current task — Universal Intake Iteration A-R3 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1 / A-R1-R1 / A-R2: **implemented and deployed**.

Universal Intake Iteration A-R3 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

## User manual E2E (R2 baseline)

PASS:
- Google file intake
- typed note
- voice note
- ordinary HTML/web URL

Observed failure motivating R3:
- `https://arxiv.org/pdf/1506.04214` → UI error «web fetch exceeded size limit»

## Iteration A-R3 scope (implemented)

- Early public HTTP classification: HTML/text vs supported direct file vs unsupported binary
- `MAX_WEB_FETCH_BYTES` = 3 MiB remains HTML/web-page cap only
- Supported direct files hand off to bounded explicit extraction (`MAX_EXPLICIT_CLOUD_DOWNLOAD_BYTES` = 20 MiB)
- `provider=web`, `kind=file`, `origin=explicit` for direct downloadable files
- Reuse shared SSRF/redirect/userinfo validation; extend `ExplicitResourceContentExtractor` for `provider=web`
- No arXiv hostname exception; no global HTML cap raise

## Deploy

Application SHA: `4abf5f82da7f566cd09ecc371e701cf62e619c45`

Deployed VDS SHA: `4abf5f82da7f566cd09ecc371e701cf62e619c45` (clean)

Encrypted context blob SHA: `99cb601b147a3e2d2b49c1fc0eab7cd9d9db7f0f`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production arXiv intake (`https://arxiv.org/pdf/1506.04214`): **PASS** — `provider=web`, `kind=file`, `content_status=ready` (no 3 MiB fetch failure)

## Next

STOP — await architect review before manual E2E.

NEXT dedicated task (not started): Universal Object Delete / Secretary-local tombstones.

Do not start format parity B or Safe External Actions.
