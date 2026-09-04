# Current task — Universal Intake Iteration A-R3-R1-R1 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1 / A-R1-R1 / A-R2: **implemented and deployed**.

Universal Intake Iteration A-R3 corrective: **implemented and deployed**; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1 corrective: **implemented and deployed** at `4bc8314c184e79417d371681e43df217a050a23d`; architect review **NOT ACCEPTED** (trusted-revision completeness, no-validator SHA revision, stale-content safety, HTML-over-suffix precedence).

Universal Intake Iteration A-R3-R1-R1 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

Architect context docs-only HEAD ancestry: `da04059905393a45871a7643b0c753f0a5194ec7`

## A-R3-R1 architect findings (application `4bc8314c184e79417d371681e43df217a050a23d`)

Functional arXiv repeat PASS, but review FAIL because:

- same-ETag fast path ignored `content_extraction_version` and actual mechanical reps
- no-validator worker never persisted `web:sha256:` revision after bounded download
- no-validator re-intake did not invalidate stale searchable content before worker
- `text/html` lost to `.pdf` URL suffix in header classification

## A-R3-R1-R1 scope (implemented)

- Unchanged READY fast path requires unchanged trusted revision + current `EXTRACTION_VERSION` + actual mechanical reps
- Stale extraction version or missing reps on same trusted revision → invalidate + one extract job
- Worker persists `web:sha256:` revision after bounded no-validator download; summary uses resolved revision
- Worker race guard aborts stale results after download if intake baseline changed
- No-validator re-intake clears mechanical/summary/embedding immediately before pending re-extraction
- Explicit `text/html` / `application/xhtml+xml` authoritative over `.pdf`/office URL suffixes
- Bounded probe behavior from A-R3-R1 preserved

## Deploy

Application SHA: `8d43328701b2d6a8111a107dc586c8256e186a26`

Deployed VDS SHA: `8d43328701b2d6a8111a107dc586c8256e186a26` (clean)

Encrypted context blob SHA: `a0e1297804443e45ff28e81c858c1e3d745ffb734e2e4d0f548f69f3ad3bbe8b`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production arXiv repeat intake (`https://arxiv.org/pdf/1506.04214`): **PASS** — same `object_id` `35717a48-5321-40c8-91b5-8cca70fd8e28`; `status=unchanged`; `content_status=ready`; `content_jobs_enqueued=0` (ETag unchanged)

## Next

STOP — await architect review before manual E2E.

NEXT dedicated task (not started): Universal Object Delete / Secretary-local tombstones.

Do not start format parity B or Safe External Actions.
