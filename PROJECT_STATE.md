# Project state

## Current phase

PHASE 18 — files, cloud resources and web links: **corrective implemented, awaiting review**

PHASE 17 — Yandex Calendar: **accepted / closed** (live-smoked)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–17: (prior phases)
- PHASE 18: resource registration API (review corrective)
  - `POST /resources/register` — Google Drive / Yandex Disk metadata, web_page, text, uploads
  - Metadata-first; explicit `ingest_content` with `content_ingested_revision` marker
  - SSRF-safe web fetch with per-hop redirect validation
  - No network during open DB transactions; worker-only object embedding
  - Bounded streaming uploads with content-hash identity

## Not done

- PHASE 18 review acceptance
- PHASE 19+ (local files, datasets tooling)

## Next phase

PHASE 19 after PHASE 18 acceptance.
