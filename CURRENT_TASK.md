# Current task — PHASE 28C-B1 awaiting architect review

## Status

PHASE 28C-A: **accepted** and deployed at `d8c17d432b53efcc992001b56840e94c17483936`.

Current: **PHASE 28C-B1 — Source Preferences UI** — implementation complete, awaiting architect review.

Do **not** merge, deploy, or start 28C-B2 until review.

## PHASE 28C-B1 delivered

- Flutter Account section «Синхронизация» for five recurring sources
- GET/PATCH `/me/source-preferences` client integration
- Per-source enable/cadence/reset with explicit JSON null clears
- Inbox `disabled` status not shown as sync error

## Branch

`review/phase-28c-source-preferences-ui` from `d8c17d432b53efcc992001b56840e94c17483936`.

## Next after 28C-B1 acceptance

PHASE 28C-B2 — History Depth Semantics & UI.

## Not in 28C-B1

- History depth (28C-B2)
- Backend functional changes
- Migration beyond Alembic `0021`
- Source «sync now»
- Drive/Disk/local recurring controls
