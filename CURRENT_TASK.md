# Current task — PHASE 29A-R1 corrective, awaiting architect review

## Status

PHASE 28D: **ARCHITECT ACCEPTED / CLOSED** at `c791461287a3b60e34c9474c9df146ea3fd8ea52`.

PHASE 29A initial: **implemented**, architect-reviewed, **not accepted**.

PHASE 29A-R1 — Retrieval, Revision & Download Trust Closure: **implemented**, **awaiting architect acceptance**.

## Branch

`review/phase-29a-bounded-content-extraction`

## PHASE 29A-R1 scope (implemented)

- Representation-aware PostgreSQL FTS retrieval (Alembic `0026` GIN indexes)
- READY re-intake idempotency (same revision preserves indexed content, zero duplicate jobs)
- Change facts before mutation (`content_revision_changed`, `title_changed`, `provider_metadata_changed`, `extraction_work_needed`)
- Immediate stale-content invalidation on revision change in intake transaction
- Defensive current-content gating for cloud providers in retrieval and `ContextService`
- Yandex download SSRF trust policy (HTTPS-only, manual redirect validation, hop limit)
- Extraction truthfulness: `no_extractable_text`, truthful `content_truncated`
- Flutter snackbars keyed on `content_status`

## Deploy

Application SHA: pending commit (corrective deploy supersedes `bbd0657`).

Alembic head: `0026` (representation FTS indexes).

Manual Google/Yandex E2E: **DEFERRED** (no safe test resources in execution environment).

## Next

STOP — await architect review. Do not start Safe External Actions or scheduled_activity.
