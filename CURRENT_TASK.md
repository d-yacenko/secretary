# Current task — PHASE 28C-A awaiting architect review

## Status

PHASE 28B-D: **accepted / deployed**. Real E2E **PASS**.

PHASE 28B-D2: **accepted / deployed** at `b39e96177fe2cdbd7fe1d385d7425ef052a0ace5`. Calendar later recovered in real runtime.

Current: **PHASE 28C-A — Per-User Source Enablement & Sync Cadence** — implementation complete, awaiting architect review.

Do **not** merge, deploy, or start 28C-B until review.

## PHASE 28C-A delivered

- `user_source_preferences` table (Alembic `0021`)
- `SourceSyncPreferenceService` with effective enable/cadence resolution
- `GET/PATCH /me/source-preferences` API
- Scheduler/worker integration: disable, cadence, running-job race, re-enable
- Source status `enabled` + `disabled` semantics

## Branch

`review/phase-28c-source-preferences-a` from `b39e96177fe2cdbd7fe1d385d7425ef052a0ace5`.

## Next after 28C-A acceptance

PHASE 28C-B — History Depth & Source Preferences UI.

## Not in 28C-A

- History depth (28C-B)
- Flutter UI changes
- Explicit Intake changes (Drive/Disk/local)
- Database migration beyond `0021`
