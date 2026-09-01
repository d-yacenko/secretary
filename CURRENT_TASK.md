# Current task — PHASE 27B-A awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **in progress**.

PHASE 27B-A — Mattermost Secure Connector & Sync Core: **implementation complete, awaiting architect review**.

Do **not** merge, deploy to production `main`, or start scheduler/UI integration until architect review.

## PHASE 27B-A delivered (backend only)

- `MattermostAccount` + migration `0019_mattermost_accounts`
- SSRF allowlist `MATTERMOST_ALLOWED_BASE_URLS`; HTTPS-only normalized base URLs; redirect rejection
- `POST /connectors/mattermost/connect` (PAT verify, encrypt at rest, no token in response; no initial sync in connect)
- Read-only Mattermost transport + bounded `MattermostSyncService`
- Normalized `Object(provider=mattermost, kind=chat_message)` → existing `embed_object` pipeline
- Focused fake-transport tests

## Not in 27B-A (next short 27B steps)

- Flutter / Inbox UI for Mattermost
- `GET /sources/status` Mattermost row
- Scheduler recurring `sync_mattermost` job
- Search/Graph UI polish
- Production deploy

## Roadmap — PHASE 27 Source Completion

- **27A** Live Source Sync, Inbox/Today & Assistant Presentation — accepted (`f92ca0c`)
- **27B** Mattermost connector — in progress (27B-A backend core done)
- **27C** Google Drive / Yandex Disk / Local Source Refresh — not started

Safe External Actions follow Source Completion.

## Deferred

- Google Drive, Yandex Disk connectors (27C)
- Local registered-folder automatic refresh (27C)
- External writes / Safe External Actions (after Source Completion)
