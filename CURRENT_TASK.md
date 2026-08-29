# Current task — PHASE 19 final corrective (implemented; awaiting final acceptance)

## Status

PHASE 19 final narrow corrective complete. Full offline suite passing. Not deployed.

PHASE 19.5 not started. PHASE 20 not started.

## Final corrective fixes

1. **Safe bounded root walk** — no symlink follow; scandir iteration; inspection cap with explicit truncated state; candidates verified under registered root before stat/hash.
2. **Large upload_copy** — streaming copy with full SHA-256 filename; no object_id pseudo-hash; revision updates produce correct stored copy.
3. **Ingest stale recheck** — re-read object before representations and before commit; stale revision/policy => no-op without embed or ingested markers.

## STOP

Awaiting PHASE 19 final acceptance. Do not start PHASE 19.5 or PHASE 20 without approval.
