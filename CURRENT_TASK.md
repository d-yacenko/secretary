# Current task — PHASE 29A-R1-R1 corrective, awaiting architect review

## Status

PHASE 28D: **ARCHITECT ACCEPTED / CLOSED** at `c791461287a3b60e34c9474c9df146ea3fd8ea52`.

PHASE 29A initial + R1: **implemented**, architect-reviewed, **not accepted**.

PHASE 29A-R1-R1 — Streaming Trust & Retrieval Visibility Closure: **implemented**, **awaiting architect acceptance**.

## Branch

`review/phase-29a-bounded-content-extraction`

## PHASE 29A-R1-R1 scope (implemented)

- True streaming Yandex download (`http.stream` + `iter_bytes` byte bound)
- Complete Yandex host/DNS/redirect trust policy (documented provider domains + resolved-address checks)
- Cloud Object title/body/trigram retrieval independent of extraction status
- Representation FTS gating only via `CLOUD_CURRENT_REPRESENTATION_SQL`
- Strict candidate pool bounded to `MAX_CANDIDATE_POOL` via deterministic round-robin merge
- Google Docs/Sheets/Slides adapter + Yandex streamed adapter + Parquet fixture tests

## Deploy

Application SHA: pending commit (supersedes `2702446`).

Alembic head: `0026` (no new migration).

Manual Google/Yandex E2E: **DEFERRED**.

## Next

STOP — await architect review. Do not start Safe External Actions or scheduled_activity.
