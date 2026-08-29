# Current task — PHASE 19 review corrective (implemented; awaiting review)

## Status

PHASE 19 review corrective complete. Full offline suite: 312 passed, 2 skipped. Not deployed.

PHASE 19.5 not started. PHASE 20 not started.

## Corrective fixes

1. **Device/filesystem isolation** — logical `device_key` in DB; filesystem dir derived via `device_keys`; mirror under `LOCAL_FILES_ROOT/<user_id>/`; traversal/symlink rejected; `LocalPathError`/`LocalAccessError` → 4xx.
2. **Shared local mirror volume** — `local_files_data` mounted in api + worker; `LOCAL_FILES_ROOT` set for both.
3. **Local resource identity** — `external_id` = `device_key` + normalized full logical path (root + relative).
4. **Bounded I/O** — no full-file reads for text/CSV/Parquet; streaming hash; truncated/sampled metadata.
5. **Ingest idempotency** — jobs carry `expected_revision` + `expected_policy`; stale/duplicate no-op; policy-only changes enqueue once.
6. **Dataset path trust** — only `LocalPathResolver` or validated upload paths under `RESOURCE_UPLOAD_ROOT/<user_id>/<object_id>/`.
7. **Bounded scan** — separate supported vs inspection caps; honest `items_truncated`; report batch `max_length`.

## STOP

Awaiting PHASE 19 review. Do not start PHASE 19.5 or PHASE 20 without approval.
