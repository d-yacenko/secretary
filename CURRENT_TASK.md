# Current task — PHASE 24 E2E corrective

## Status

PHASE 24: **accepted / closed** at `e128f26414c1ffb33d6040c2d87e2b2054e35480`.

VDS: deployed `e128f26` on 2026-08-30 (matched-version manual E2E baseline).

Manual E2E findings (post-deploy):

1. Graph keeps stale workspace after Assistant create/update until Return to Overview.
2. Direct Delete leaves a `deleted` node on screen until Return to Overview.
3. Legacy active tasks with `state=proposed` / `status=proposed` excluded from default Graph overview.

Post-deploy corrective implemented on branch `review/phase-24-e2e-corrective`:

- Graph tab activation refreshes current workspace (overview or rooted root).
- Canonical active-task seed semantics (non-rejected, non-terminal status).
- Lifecycle-aware `applyTaskMutation` removes deleted/terminal tasks from active overview immediately.
- Rooted delete falls back to refreshed overview.
- Missing-root 404 on rooted refresh falls back to overview.
- Object Detail opened from Graph reconciles workspace on return.

**Awaiting architect acceptance.** Do not deploy until accepted.

Do not claim final Graph manual E2E PASS yet.

## STOP

Do not start the next product phase.
