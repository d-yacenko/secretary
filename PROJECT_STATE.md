# Project state

## Current phase

PHASE 18 — files, cloud resources and web links: **corrective implemented, awaiting final acceptance**

PHASE 17 — Yandex Calendar: **accepted / closed** (live-smoked)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–17: (prior phases)
- PHASE 18: resource registration API (final corrective)
  - Stable identity via `provider+external_id` or `canonical_uri` (revision never identifies resources)
  - SSRF-safe web fetch; no network during open DB transactions
  - Worker `embed_object` embeds object + unembedded chunk representations post-commit
  - Bounded JSON/multipart payloads and streaming uploads
  - Persistent Docker volume-backed upload storage (`resource_data`)

## Not done

- PHASE 18 final acceptance
- PHASE 19+ (local files, datasets tooling)

## Next phase

PHASE 19 after PHASE 18 acceptance.
