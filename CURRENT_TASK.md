# Current task — PHASE 18 bounded representation corrective

## Status

**corrective implemented, awaiting final acceptance**

## Fixes delivered

1. **Bounded text chunks** — `MAX_INDEXED_TEXT_CHUNKS=64`; deterministic spread selection; indexing metadata on chunk representations
2. **Worker** — object embed + bounded chunk embeds; no network in DB transaction
3. **Same-hash reupload** — preserve `upload_path`; update display filename only; skip re-ingest when revision ingested
4. **Multipart** — parser `max_part_size` + post-parse payload bound; 413 handler for oversized parts on register

## STOP

PHASE 19 not started. Awaiting PHASE 18 final acceptance.
