# Project state

## Current phase

PHASE 19 — local files and huge datasets: **implemented, awaiting review**

PHASE 18 — resource registration: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–18: (prior phases)
- PHASE 19: local files and datasets
  - User-scoped device/root registration; no global filesystem crawl
  - Bounded root scan and file report batches
  - Skip re-ingest when file revision unchanged
  - Worker `ingest_local_file` verifies ownership before mirror access
  - Dataset tools return schema/sample/stats/column queries without full prompt dump

## Not done

- PHASE 19 review acceptance
- PHASE 19.5+ (auth, Flutter)

## Next phase

PHASE 19.5 after PHASE 19 acceptance.
