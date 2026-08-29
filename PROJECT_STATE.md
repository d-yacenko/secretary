# Project state

## Current phase

PHASE 18 — files, cloud resources and web links: **implemented, awaiting review**

PHASE 17 — Yandex Calendar: live-smoked, awaiting final acceptance

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–17: (prior phases)
- PHASE 18: resource registration API
  - `POST /resources/register` — Google Drive / Yandex Disk metadata, web_page stubs, text, uploads
  - Metadata-first; `ingest_content` for bounded extract/representations
  - Revision-aware skip (no repeat embed/extract when unchanged)
  - User-scoped; tasks link via existing graph edges (`attached_to`, etc.)

## Not done

- PHASE 17 final acceptance
- PHASE 18 review acceptance
- PHASE 19+ (local files, datasets tooling)

## Next phase

PHASE 19 after PHASE 18 acceptance.
