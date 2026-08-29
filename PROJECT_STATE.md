# Project state

## Current phase

PHASE 18 — files, cloud resources and web links: **corrective implemented, awaiting final acceptance**

PHASE 17 — Yandex Calendar: **accepted / closed** (live-smoked)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–17: (prior phases)
- PHASE 18: resource registration API (bounded representation corrective)
  - Stable identity; worker embeddings; volume-backed uploads; deferred ingest metadata
  - Bounded indexed text chunks (`MAX_INDEXED_TEXT_CHUNKS=64`) with truncation metadata
  - Same-hash upload reupload preserves stored source reference

## Not done

- PHASE 18 final acceptance
- PHASE 19+ (local files, datasets tooling)

## Next phase

PHASE 19 after PHASE 18 acceptance.
