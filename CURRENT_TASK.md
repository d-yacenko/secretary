# Current task — PHASE 27A awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress** (27A implementation complete, awaiting architect review).

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **implementation complete, awaiting architect review**.

PHASE 26 — Personal Data Correlation: **accepted / closed** (`5c4ffc40`).

Do **not** merge, deploy to production `main`, or start PHASE 27B until architect review.

## PHASE 27A delivered

- Recurring source sync jobs (`sync_google_gmail`, `sync_google_calendar`, `sync_yandex_mail`, `sync_yandex_calendar`) with same-row reschedule
- `SourceSyncScheduler` worker maintenance (≈60s) without duplicate schedules
- `GET /sources/status`, `POST /sources/sync`, `GET /inbox` aggregate snapshot
- Inbox Flutter: «Требует внимания» + «Последние из источников»
- Today includes active proposed tasks with «Предложено» marker
- Assistant Markdown rendering via `flutter_markdown`
- Compact `Я` badge for `yandex_calendar`, `G` for `google_calendar`

## Roadmap — PHASE 27 Source Completion

- **27A** Live Source Sync, Inbox/Today & Assistant Presentation (this phase)
- **27B** Mattermost connector (not started)
- **27C** Google Drive / Yandex Disk / Local Source Refresh (not started)

Safe External Actions follow Source Completion.

## Deferred

- Mattermost, Google Drive, Yandex Disk connectors (27B/27C)
- Local registered-folder automatic refresh (27C)
- External writes / Safe External Actions (after Source Completion)
