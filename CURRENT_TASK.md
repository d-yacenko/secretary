# Current task — PHASE 27B-B awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **in progress**.

PHASE 27B-A — Mattermost Secure Connector & Sync Core: **accepted / closed** (`87b16cb`).

PHASE 27B-B — Mattermost Operational Backend Integration: **implementation complete, awaiting architect review**.

Do **not** merge, deploy to production `main`, or start PHASE 27B-C (Flutter UX) until architect review.

## PHASE 27B-B delivered (backend only)

- Recurring `sync_mattermost` job in `RECURRING_SOURCE_JOB_TYPES`; payload `account_id` only; default interval 120s (`SOURCE_SYNC_MATTERMOST_INTERVAL_SECONDS`)
- Worker handler via existing `source_sync_handlers` + `HANDLERS`; PAT loaded from user-owned `MattermostAccount`
- `SourceSyncScheduler`: one recurring row per Mattermost account; stale retirement; failed rearm; `trigger_all_for_user` includes Mattermost
- `POST /sources/sync` triggers Mattermost recurring rows (no inline network sync)
- `GET /sources/status` includes `mattermost` provider row (no PAT)
- `GET /connections` exposes Mattermost account list (non-secret fields only)
- Trusted `OpenTarget` for `provider=mattermost`, `kind=chat_message` (allowlisted server base + bounded metadata; team post deep link or server fallback)
- Stronger `sanitize_job_error` for Authorization/Bearer/token needles
- Focused operational integration tests (`test_phase_27b_operational.py`)

## Not in 27B-B (next: 27B-C)

- Flutter Mattermost UX
- Matched-version E2E
- Mattermost disconnect flow
- Production deploy

## Roadmap — PHASE 27 Source Completion

- **27A** Live Source Sync, Inbox/Today & Assistant Presentation — accepted (`f92ca0c`)
- **27B** Mattermost connector — in progress (27B-B operational backend done)
- **27C** Google Drive / Yandex Disk / Local Source Refresh — not started

Safe External Actions follow Source Completion.

## Deferred

- Google Drive, Yandex Disk connectors (27C)
- Local registered-folder automatic refresh (27C)
- External writes / Safe External Actions (after Source Completion)
