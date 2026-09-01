# Current task — PHASE 27C-A awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **accepted / closed** (application SHA `1dc493d`; user Mattermost E2E accepted).

PHASE 27C — Google Drive / Yandex Disk / Local Source Refresh: **started**.

PHASE 27C-A — Google Drive Read-Only Foundation: **implementation complete, awaiting architect review**.

Do **not** merge, deploy to production `main`, or start PHASE 27C-B until architect review.

## PHASE 27C-A delivered

- OAuth: `drive.readonly` added to `GOOGLE_OAUTH_SCOPES` (with existing `prompt=consent`)
- `drive_available` on Google connection snapshot (`/connections`)
- Migration `0020`: `GoogleAccount.drive_sync_state` JSONB for provider cursors
- Drive connector: transport (`files.list`, `changes.list`, `startPageToken`), normalize, bounded bootstrap + incremental sync
- Canonical Objects: `provider=google_drive`, `kind=file|folder`, soft-delete via `status=deleted`
- Manual endpoint: `POST /connectors/google/drive/sync` (optional `account_id`)
- Focused tests: `test_phase_27c_google_drive.py`

## Not in 27C-A

- Flutter Drive UI
- Recurring `sync_google_drive` scheduler / `/sources/status`
- Drive file content download / Google Docs export
- OpenTarget UI for Drive
- Yandex Disk
- Local folder refresh
- Graph parent edges (only `metadata.parents`)

## Roadmap — PHASE 27 Source Completion

- **27A** — accepted (`f92ca0c`)
- **27B** Mattermost — accepted (`1dc493d`)
- **27C** Drive/Disk/local refresh — in progress (27C-A done, awaiting review)

Safe External Actions follow Source Completion.
