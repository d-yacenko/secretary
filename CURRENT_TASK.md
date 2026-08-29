# Current task — PHASE 19 (implemented; awaiting review)

## Status

PHASE 19 code complete. Offline tests pass. Not deployed.

## Goal

Register local desktop resources without forcing upload; bounded dataset tooling.

## Implemented

- User-scoped `local_devices` + `local_roots` (migration `0013`)
- Mirror filesystem under `local_files_root` with path traversal guards
- `POST /local/devices/register`, `/local/roots/register`, `/local/roots/{id}/scan`, `/local/files/report`
- Policies: `metadata_only` (default), `index_text`, `upload_copy`
- Objects: `provider=local_device`, `personal://device/<key>/file/<object-id>` URI
- Stable identity via path-based `external_id`; revision from size/mtime/hash
- Worker job `ingest_local_file` with ownership check before filesystem access
- Dataset tools API: schema, sample, stats, column query (bounded rows)

## Defer

- Real auth/session (PHASE 19.5)
- Flutter client (PHASE 20+)
- Desktop sync agent (uses report/scan APIs)

## STOP

Awaiting PHASE 19 review. Do not start PHASE 19.5 or PHASE 20 without approval.
