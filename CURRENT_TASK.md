# Current task — PHASE 19 (awaiting final acceptance)

## Status

PHASE 19 final corrective complete including Python 3.12 walk compatibility and honest supported-cap truncation. Full offline suite passing. Not deployed.

PHASE 19.5 not started. PHASE 20 not started.

## Recent fixes

1. **Python 3.12 walk** — no `Path.is_dir(follow_symlinks=...)`; symlink-safe dir checks via `is_symlink()` + `is_dir()`; `DirEntry` follow_symlinks kwargs retained.
2. **Honest supported cap** — `items_truncated=true` only when candidates were actually omitted (supported/inspection/traversal bounds).

## STOP

Awaiting PHASE 19 final acceptance. Do not start PHASE 19.5 or PHASE 20 without approval.
