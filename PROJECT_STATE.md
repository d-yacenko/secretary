# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **closure corrective implemented, awaiting final acceptance**

PHASE 22.5B — not started

PHASE 23 — voice: **not started**

PHASE 22 — Search and Assistant UI: **accepted / closed**

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–22: (prior phases, PHASE 22 closed)
- PHASE 22.5A (awaiting final acceptance):
  - `Object.occurred_at` (migration `0016`) with keyset-paginated fail-safe email backfill
  - PostgreSQL FTS + `pg_trgm` indexes (expression GIN + title trigram)
  - `RetrievalService`: ordered indexed candidate branches (50 FTS + 50 trigram), bounded pool (100)
  - `match_quality` vs `ranking_score` — anchor/recency bonuses cannot manufacture qualification
  - Progressive horizon (90d → 365d → all-history); stops only on strong textual match
  - Explicit date bounds (`date_from` / `date_to` / both); rejects inverted ranges
  - Time-sensitive sources with `occurred_at=NULL` never receive recency from `created_at`
  - `SearchService` delegates to `RetrievalService` (all-history UI semantics, no embeddings)
  - Connector upserts populate `occurred_at` for Gmail/Yandex mail and calendar events
  - `test_retrieval.py` + `test_migration_0016.py` regression suite
  - VDS deploy deferred (PHASE 22.5A)

## Not done

- PHASE 22.5B
- PHASE 23 voice
- Assistant wired to `RetrievalService` (deferred)
- Graph editor, persistent assistant chat DB

## Next phase

PHASE 22.5A final acceptance. PHASE 22.5B not started. PHASE 23 not started.
