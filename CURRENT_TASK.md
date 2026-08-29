# Current task — PHASE 22.5A

## Status

PHASE 22.5A final corrective implemented. STOP for review.

PHASE 22 accepted / closed. PHASE 22.5B not started. PHASE 23 not started. No VDS deploy.

## Delivered (final corrective)

- Indexed two-stage candidate SQL (`@@` combined FTS document, `%` trigram); rank only bounded candidates
- `match_quality` / `ranking_score` separation; qualification from textual evidence only
- Horizon expansion stops only on strong textual match, not weak anchor/recency noise
- Fail-safe migration `0016` email backfill (Python batches, malformed timestamps stay NULL)
- `occurred_at=NULL` time-sensitive sources: no recency bonus from `created_at`
- Explicit `date_from` / `date_to` bounds; reject `date_from > date_to`
- Regression tests: indexed SQL, horizon widen, recency, date bounds, migration backfill

## STOP

Await PHASE 22.5A review. Do not start PHASE 22.5B or PHASE 23. Do not deploy to VDS.
