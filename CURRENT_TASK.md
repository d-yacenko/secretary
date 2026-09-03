# Current task — PHASE 28C-R1-R1 awaiting review

## Status

PHASE 28C-B2-D: **accepted** at `e8680f2105348cdd9220f8de3d9ff8a25ed6f431`.

Manual PHASE 28C history E2E: **PASS** — increased Gmail history produced progressively older mail without sync errors.

PHASE 28C-R1 — Inbox Recent Ordering + Stale Sync Banner Cleanup: **accepted** at `b62f7978647d9a4767c6040ff84df0e611e9f1b5`.

Current: **PHASE 28C-R1-R1 — Eliminate Sync Banner Settlement Race** — implemented, awaiting architect review.

Do **not** merge, deploy, or start Phase 29 until review.

## Branch

`review/phase-28c-inbox-recent-ordering-r1-r1` from `b62f7978647d9a4767c6040ff84df0e611e9f1b5`.

## Next after R1-R1 acceptance/deploy

**PHASE 29A — bounded content extraction**.

## Not in 28C-R1-R1

- Phase 29
- RecentSourceService ordering changes
- backend sync/history runtime
- migration (Alembic stays 0023)
- deploy / merge
