# Current task — PHASE 28B-D2-R1 awaiting architect review

## Status

PHASE 28B-D — Source Status Diagnostics & UI Freshness: **accepted / deployed**. Real E2E **PASS**.

PHASE 28B-D2 — Yandex Calendar CalDAV Regression & Credential Corrective: **implementation complete**, awaiting architect review on branch `review/phase-28b-yandex-calendar-caldav`.

Real E2E after D2 corrective: Yandex Calendar **recovered** — new Calendar event arrived.

Current: **PHASE 28B-D2-R1 — Yandex CalDAV Safety / Retry Corrective** — implementation complete, awaiting architect review.

Do **not** merge, deploy, or start 28C until review.

## PHASE 28B-D2-R1 delivered

- Trusted CalDAV host allowlist (`caldav.yandex.ru` only); HTTPS-only; no credentials to arbitrary hosts
- CalDAV transport disables redirect following
- Yandex Mail `YandexImapError` retry regression fixed (CalDAV typed retry unchanged)

## Branch

`review/phase-28b-yandex-calendar-caldav-r1` from `014e689f8ec84ee54992708ec190dd8779cdeb3a`.

## Approved next after D2-R1 acceptance/deploy/E2E

PHASE 28C — Per-User Source/Sync Preferences.

## Not in 28B-D2-R1

- Database migration (Alembic remains `0020`)
- Calendar write support
- Source cadence preferences (28C)
- Google / Yandex Disk / MCP changes
- WebSocket/SSE
