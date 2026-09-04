# Current task — Universal Intake Iteration A-R3-R1 deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **implemented**, **not architect-accepted**.

Universal Intake Iteration A-R1 / A-R1-R1 / A-R2: **implemented and deployed**.

Universal Intake Iteration A-R3 corrective: **implemented and deployed**; architect review **NOT ACCEPTED** (bounded probe still drained binary streams; ready re-intake idempotency; untrustworthy URL+length revision; text file classification gaps).

Universal Intake Iteration A-R3-R1 corrective: **implemented and deployed**, **awaiting architect review and manual E2E**.

## Branch

`review/universal-intake-format-parity-a`

## A-R3 architect findings (application `4abf5f82da7f566cd09ecc371e701cf62e619c45`)

Functional arXiv PASS (`provider=web`, `kind=file`, `content_status=ready`), but review FAIL because:

- intake probe drained supported/unsupported binary bodies to EOF despite `store=False`
- `apply_intake_content_metadata()` set `pending` before same-revision unchanged return (`ready → pending`, jobs=0)
- `web:url-cl:{final_url}:{content_length}` used as revision without trustworthy validator
- `text/plain` / `text/csv` / `text/markdown` not classified as direct files before binary split

## A-R3-R1 scope (implemented)

- Bounded probe: header-first where sufficient; otherwise explicit `iter_bytes(chunk_size=4096)` prefix only; stop immediately after supported/unsupported binary classification; HTML continues on same iterator
- Declared `Content-Length` > 20 MiB supported file → `too_large` metadata object, zero body bytes when headers suffice
- Ready re-intake with unchanged trusted revision preserves extraction status, mechanical reps, summary, embedding; zero extract jobs
- Remove `web:url-cl:` revision; no-validator re-intake conservatively re-extracts once (same `object_id`)
- Direct text file classification (`txt`/`md`/`csv`) before generic binary/HTML split
- Stream-bound regression tests prove bytes consumed, not just metadata

## Deploy

Application SHA: `4bc8314c184e79417d371681e43df217a050a23d`

Deployed VDS SHA: `4bc8314c184e79417d371681e43df217a050a23d` (clean)

Encrypted context blob SHA: `9bed8f596fdf0d03194b2fea968d881efddc6b109e7b8c1667f0c19f9bebb315`

Alembic current/head: `0026`

`/health`: PASS

Worker: healthy

Production arXiv repeat intake (`https://arxiv.org/pdf/1506.04214`): **PASS** — same `object_id` `35717a48-5321-40c8-91b5-8cca70fd8e28`; `status=unchanged`; `content_status=ready`; `content_jobs_enqueued=0` (ETag unchanged)

## Next

STOP — await architect review before manual E2E.

NEXT dedicated task (not started): Universal Object Delete / Secretary-local tombstones.

Do not start format parity B or Safe External Actions.
