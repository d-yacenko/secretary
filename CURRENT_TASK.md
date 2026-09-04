# Current task — Universal Intake Iteration A final concurrency closure deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1 / A-R1-R1 / A-R2: **implemented and deployed**.

Universal Intake Iteration A-R3 corrective: **implemented and deployed**; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1 corrective: **implemented and deployed** at `4bc8314c184e79417d371681e43df217a050a23d`; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1-R1 corrective: **implemented and deployed** at `8d43328701b2d6a8111a107dc586c8256e186a26`; architect review **NOT ACCEPTED**.

Universal Intake Iteration A-R3-R1-R1-R1 corrective: **implemented and deployed** at `8734faac62ca7ad58611a118e99b3b83e2b69f04`; architect review **NOT ACCEPTED**.

Universal Intake Iteration A final concurrency closure: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

Architect context docs-only HEAD ancestry: `da04059905393a45871a7643b0c753f0a5194ec7`

## A-R3-R1-R1-R1 architect findings (application `8734faac62ca7ad58611a118e99b3b83e2b69f04`)

Functional arXiv repeat PASS, but review FAIL because:

- early worker flush of no-validator SHA/revision before parse held row locks and blocked concurrent intake
- final persist was not atomic under `FOR UPDATE` after parse
- no-validator explicit re-intake lacked generation-based supersession for concurrent workers

## Final concurrency closure scope (implemented)

- No early `metadata_` flush of `resolved_content_hash` / `resolved_revision` before mechanical parse for no-validator `provider=web`
- `_persist_success_if_authoritative()` / `_fail_if_authoritative()` use `acquire_worker_final_authority()` (`SELECT ... FOR UPDATE`, `session.refresh`, baseline/revision/extraction_version checks)
- `web_revalidation_generation` increments on explicit no-validator re-intake; successor extract jobs enqueue when baseline changes
- Deterministic interleaved concurrency tests via `extract_from_path` hook (no threads/asyncio/sleeps)
- A-R3-R1-R1-R1 baseline authority, race-safe failures, bounded probe, idempotency, HTML precedence preserved

## Deploy

Application SHA: `f5b76856b4c967ef0673798bd6e9334c77fd2522`

Deployed VDS SHA: `f5b76856b4c967ef0673798bd6e9334c77fd2522` (clean)

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production arXiv repeat intake (`https://arxiv.org/pdf/1506.04214`): **PASS** — same `object_id` `35717a48-5321-40c8-91b5-8cca70fd8e28`; `status=unchanged`; `content_status=ready`; `content_jobs_enqueued=0` (ETag unchanged)

## Next

STOP — await architect review before manual E2E.

NEXT dedicated task (not started): Universal Object Delete / Secretary-local tombstones.

Do not start format parity B or Safe External Actions.
