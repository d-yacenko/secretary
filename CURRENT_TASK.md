# Current task — PHASE 18 final narrow corrective

## Status

**corrective implemented, awaiting final acceptance**

## Fixes delivered (narrow corrective)

1. **System metadata preservation** — deferred ingest reuses `upload_path`, `content_revision`, `content_hash`, `upload_filename`; sets `content_ingested_revision` on success; third identical ingest is unchanged
2. **Failure cleanup** — newly persisted upload orphans removed on extraction failure; prior valid revision file retained
3. **Multipart bound** — `Request.form(max_part_size=MAX_UPLOAD_BYTES)` with `MultiPartException` → 413; payload field also bounded post-parse via `MAX_MULTIPART_PAYLOAD_BYTES`

## PHASE 18 invariants

- User-owned registration; stable identity; worker-only embeddings
- System-managed upload metadata survives ingest-only follow-up requests

## STOP

PHASE 19 not started. Awaiting PHASE 18 final acceptance.
