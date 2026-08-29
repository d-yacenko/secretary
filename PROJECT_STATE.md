# Project state

## Current phase

PHASE 18 — files, cloud resources and web links: **corrective implemented, awaiting final acceptance**

PHASE 17 — Yandex Calendar: **accepted / closed** (live-smoked)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–17: (prior phases)
- PHASE 18: resource registration API (final narrow corrective)
  - Stable resource identity; worker chunk embeddings; volume-backed uploads
  - System metadata preserved across deferred ingest (`upload_path`, revisions, filenames)
  - Upload orphan cleanup on failed extraction without deleting prior revision files

## Not done

- PHASE 18 final acceptance
- PHASE 19+ (local files, datasets tooling)

## Next phase

PHASE 19 after PHASE 18 acceptance.
