# Current task — PHASE 28B-D2 awaiting architect review

## Status

PHASE 28B — Per-User Background AI Runtime: **accepted / closed** at `76b133b10ea2408e11c66e3fe1701a59a47bc828`.

PHASE 28B-D — Source Status Diagnostics & UI Freshness: **accepted / deployed**. Real E2E **PASS**:
- source error diagnostics PASS
- Yandex Mail PASS
- Inbox desktop passive refresh PASS
- new mail appeared automatically without tab switch

Open corrective: Yandex Calendar recurring CalDAV sync failure.

Current: **PHASE 28B-D2 — Yandex Calendar CalDAV Regression & Credential Corrective** — implementation complete, awaiting architect review.

Do **not** merge, deploy, or start 28C until review.

## PHASE 28B-D2 delivered

- Typed CalDAV failure model (auth/permission/not_found/rate_limit/server/network) with safe user-visible messages
- Job retry classification respects CalDAV retryability; stale sync-token recovery preserved
- Calendar connect validates credentials before overwrite; transient failures do not destroy stored credential
- Account Yandex dialog: separate Mail and Calendar app-password fields; service-scoped connect calls
- Live safe probe on matched deployment: HTTP 401 on principal PROPFIND; stored Mail/Calendar passwords equal

## Branch

`review/phase-28b-yandex-calendar-caldav` from `47acf9c64a62b8ad87f3264732eed631fb1d21dd`.

## Approved next after D2 acceptance/deploy/E2E

PHASE 28C — Per-User Source/Sync Preferences.

## Not in 28B-D2

- Database migration (Alembic remains `0020`)
- Calendar write support
- Source cadence preferences (28C)
- Google / Yandex Disk / MCP changes
- WebSocket/SSE
- Large Account redesign
