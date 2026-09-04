# Current task — Universal Intake Iteration A-R3-R1-R1-R1 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1 / A-R1-R1 / A-R2: **implemented and deployed**.

Universal Intake Iteration A-R3 corrective: **implemented and deployed**; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1 corrective: **implemented and deployed** at `4bc8314c184e79417d371681e43df217a050a23d`; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1-R1 corrective: **implemented and deployed** at `8d43328701b2d6a8111a107dc586c8256e186a26`; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1-R1-R1 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

Architect context docs-only HEAD ancestry: `da04059905393a45871a7643b0c753f0a5194ec7`

## A-R3-R1-R1 architect findings (application `8d43328701b2d6a8111a107dc586c8256e186a26`)

Functional arXiv repeat PASS, but review FAIL because:

- `fetched_at` was treated as worker content identity and aborted valid extractions on harmless same-URL re-intake
- queue dedupe did not align with extraction baseline supersession
- failure paths (`too_large`, parser failure) could overwrite newer pending/ready state
- `_mechanical_rep_count` counted summary rows as mechanical reps

## A-R3-R1-R1-R1 scope (implemented)

- Deterministic `extraction_baseline` token for `provider=web` (final URL, suffix, format, trusted remote revision, `EXTRACTION_VERSION`; **not** `fetched_at`)
- Worker authority + queue dedupe include `extraction_baseline` in job payload/comparison
- Same-ETag / same-baseline concurrent re-intake does not abort running worker
- E1→E2 trusted revision supersession: stale worker aborts; successor extract job enqueued; failure paths race-safe
- Mechanical rep checks count only `full|chunk|schema|sample|statistics`
- Bounded probe / idempotency / no-validator SHA / HTML precedence / A-R3-R1-R1 regressions preserved

## Deploy

Application SHA: `8734faac62ca7ad58611a118e99b3b83e2b69f04`

Deployed VDS SHA: `8734faac62ca7ad58611a118e99b3b83e2b69f04` (clean)

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production arXiv repeat intake (`https://arxiv.org/pdf/1506.04214`): **PASS** — same `object_id` `35717a48-5321-40c8-91b5-8cca70fd8e28`; `status=unchanged`; `content_status=ready`; `content_jobs_enqueued=0` (ETag unchanged)

## Next

STOP — await architect review before manual E2E.

NEXT dedicated task (not started): Universal Object Delete / Secretary-local tombstones.

Do not start format parity B or Safe External Actions.
