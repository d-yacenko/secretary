# Current task — PHASE 22.5A

## Status

PHASE 22.5A Local Retrieval Foundation implemented. STOP for review.

PHASE 22 accepted / closed. PHASE 22.5B not started. PHASE 23 not started. No VDS deploy.

## Delivered

- Migration `0016`: `occurred_at`, `pg_trgm`, FTS/trigram indexes, safe backfill
- `RetrievalService` + `SearchService` wrapper (PostgreSQL FTS/trigram, no embeddings)
- Progressive time-sensitive source horizon; personal objects not age-filtered
- Connector `occurred_at` on Gmail/Yandex mail and calendar ingest
- `test_retrieval.py` (isolation, top-K max, nornickel fixture, horizons, occurred_at, bounds)

## STOP

Await PHASE 22.5A review. Do not start PHASE 22.5B or PHASE 23. Do not deploy to VDS.
