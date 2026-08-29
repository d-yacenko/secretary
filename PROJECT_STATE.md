# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **implemented, awaiting review**

PHASE 22.5B — not started

PHASE 23 — voice: **not started**

PHASE 22 — Search and Assistant UI: **accepted / closed**

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–22: (prior phases, PHASE 22 closed)
- PHASE 22.5A (awaiting review):
  - `Object.occurred_at` (migration `0016`) with safe backfill for email/calendar
  - PostgreSQL FTS + `pg_trgm` indexes (expression GIN + title trigram)
  - `RetrievalService`: user-scoped filter-first, progressive horizon (90d → 365d → all-history)
  - Deterministic ranking (FTS, trigram, anchor-kind boost, recency secondary)
  - Top-K as maximum with `MIN_HIT_SCORE`; structured `RetrievalHit` results
  - `SearchService` delegates to `RetrievalService` (all-history UI semantics, no embeddings)
  - Connector upserts populate `occurred_at` for Gmail/Yandex mail and calendar events
  - `test_retrieval.py` focused regression suite (11 tests)
  - `pytest` 425 passed; `ruff check .` passes
  - VDS deploy deferred (PHASE 22.5A)

## Not done

- PHASE 22.5B
- PHASE 23 voice
- Assistant wired to `RetrievalService` (deferred)
- Graph editor, persistent assistant chat DB

## Next phase

PHASE 22.5A review. PHASE 22.5B not started. PHASE 23 not started.
