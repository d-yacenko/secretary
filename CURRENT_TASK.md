# Current task — PHASE 29A, awaiting final user E2E

## Status

PHASE 28D: **ARCHITECT ACCEPTED / CLOSED** at `c791461287a3b60e34c9474c9df146ea3fd8ea52`.

PHASE 29A initial + R1 + R1-R1: **implemented**, production E2E failure diagnosed, **not accepted**.

PHASE 29A-R2 — XLSX Searchable Content & Context Closure: **implemented**, architect code review **PASS**.

PHASE 29A-R2-R1 — Assistant retrieve `kind="all"` normalization: **implemented**, architect code review **PASS**, **deployed**.

PHASE 29A overall: **awaiting final user E2E** (manual retest after R2-R1 deploy).

## Branch

`review/phase-29a-bounded-content-extraction`

## PHASE 29A-R2 scope (implemented)

- XLSX sparse cell parsing with real row numbers and column positions
- Searchable full/chunk representations from all bounded worksheet rows
- `EXTRACTION_VERSION` bump to `phase29a-v2`
- Version-aware cloud Representation retrieval gate
- Same-revision v1→v2 re-intake schedules extraction
- Assistant `get_context` optional `query` parameter
- Lexical chunk ranking fallback without embeddings
- CLI bounded stale-v1 cloud reindex maintenance path

## PHASE 29A-R2-R1 scope (implemented)

- Assistant retrieve `kind` wildcard normalization (`all`/`any`/`*`/blank → no filter)
- Contract clarifies optional exact `Object.kind` filter

## Deploy

Application SHA: `1562db7a7764e387ce4c9518a7032b801fcf0cdf`

Deployed VDS SHA: `1562db7a7764e387ce4c9518a7032b801fcf0cdf` (clean working tree)

Alembic current/head: `0026` (no new migration).

`/health`: PASS (`{"status":"ok"}`).

Worker: healthy (Up).

Production direct Assistant tool-path check (`retrieve`, `kind="all"`): **PASS** — `kind` normalized to `null`, target `Второе полугодие.xlsx` in top-5.

Production direct Assistant tool-path check (`retrieve`, `kind="file"`): **PASS** — target returned.

Manual Google/Yandex E2E: **DEFERRED** — await user retest on deployed SHA.

## Next

STOP — await final user E2E. Do not start Safe External Actions or scheduled_activity.
