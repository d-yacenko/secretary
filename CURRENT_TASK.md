# Current task — PHASE 27B-C awaiting architect + user E2E

## Status

PHASE 27 — Source Completion: **in progress** (until manual matched-version E2E acceptance).

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **in progress**.

PHASE 27B-A — Mattermost Secure Connector & Sync Core: **accepted / closed** (`87b16cb`).

PHASE 27B-B — Mattermost Operational Backend Integration: **accepted / closed** (`96a5249`).

PHASE 27B-C — Mattermost Flutter UX + matched-version E2E prep: **implementation complete, awaiting architect review + user matched-version E2E**.

Do **not** merge, deploy to production `main`, or start PHASE 27C until 27B manual E2E acceptance.

## PHASE 27B-C delivered

- Flutter `MattermostConnection` model + `Connections.mattermost[]`
- `SecretaryApiClient.connectMattermost(serverUrl, accessToken)` — PAT not stored/logged
- Account → Подключения: list Mattermost accounts, connect dialog (Server URL + obscured PAT)
- Provider presentation: glyph `M`, label `Mattermost` for `chat_message` in existing Inbox/Search/Graph UI
- Generic source status + backend OpenTarget flow unchanged (trusted server from backend)
- Backend connect: `ensure_recurring_source_job(sync_mattermost)` + trigger runnable now (no inline sync)
- Focused Flutter + backend tests

## Manual E2E (user, matched-version build)

1. Аккаунт → Подключения → Подключить Mattermost
2. Allowlisted server + PAT → account in list
3. Mattermost in source status
4. First read-only sync → messages in Inbox/recent
5. Search known phrase → Open in Mattermost
6. Assistant query with Mattermost evidence
7. PAT not visible in UI/status/errors

## Not in 27B-C

- Mattermost disconnect
- Production deploy
- PHASE 27C (Drive/Disk/local refresh)

## Roadmap — PHASE 27 Source Completion

- **27A** — accepted (`f92ca0c`)
- **27B** Mattermost — in progress (27B-C done, E2E pending)
- **27C** Google Drive / Yandex Disk / Local Source Refresh — not started

Safe External Actions follow Source Completion.
