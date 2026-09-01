# Current task — PHASE 27C-B awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **accepted / closed** (`1dc493d`).

PHASE 27C — Google Drive / Yandex Disk / Local Source Refresh: **in progress**.

PHASE 27C-A — Google Drive Read-Only Foundation: **accepted / closed** (`2a4145f`).

PHASE 27C-B — Google Drive Recurring Sync + Trusted OpenTarget: **implementation complete, awaiting architect review**.

Do **not** merge, deploy to production `main`, or start content ingestion until architect review.

## PHASE 27C-B delivered

- Recurring job `sync_google_drive` (300s default) in existing scheduler/worker lifecycle
- `POST /sources/sync` triggers Drive row; `GET /sources/status` shows `google_drive`
- Trusted OpenTarget: `Открыть в Google Drive` from verified `account_id` + `file_id` only
- Focused tests: `test_phase_27c_operational.py`
- `POST /connectors/google/drive/sync` retained as direct connector/debug path (27C-A)

## Not in 27C-B

- Drive content download / export / Docs indexing
- Flutter Drive UI
- Yandex Disk
- Merge to `main`, production deploy

## Roadmap — PHASE 27 Source Completion

- **27A** — accepted (`f92ca0c`)
- **27B** Mattermost — accepted (`1dc493d`)
- **27C** Drive/Disk/local refresh — in progress (27C-A closed, 27C-B awaiting review)

Safe External Actions follow Source Completion.
