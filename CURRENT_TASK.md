# Current task — PHASE 28B-D awaiting architect review

## Status

PHASE 28B — Per-User Background AI Runtime: **accepted / closed** at `76b133b10ea2408e11c66e3fe1701a59a47bc828`.

Deployment: **PASS**.

Manual matched-version checks:
- Assistant PASS
- direct task mutation PASS
- Assistant approval/action plan PASS
- MCP manual E2E deferred

Current: **PHASE 28B-D — Source Status Diagnostics & UI Freshness** — implementation complete, awaiting architect review.

Do **not** merge, deploy, or start 28C until review.

## PHASE 28B-D delivered

- Per-source sync error cards in Inbox (provider, account label, safe reason, timing)
- Source errors visible when Inbox has no notifications/objects
- Passive snapshot refresh scheduler fix (paused tick no longer stops polling)
- Manual source refresh `try/finally` resets `_isSourceRefreshing` on all paths
- Inbox/Today passive refresh survives manual refresh overlap and failure

## Branch

`review/phase-28b-source-ui-freshness` from `76b133b10ea2408e11c66e3fe1701a59a47bc828`.

## Approved next after acceptance/deploy

PHASE 28C — Per-User Source/Sync Preferences.

## Not in 28B-D

- Source sync preferences (28C)
- WebSocket/SSE
- Database migration
- MCP work
