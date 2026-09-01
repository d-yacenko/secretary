# Current task — PHASE 27C-R1 awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **accepted / closed** (`1dc493d`).

PHASE 27B-A — Mattermost Secure Connector & Sync Core: **accepted / closed** (`87b16cb`).

PHASE 27B-B — Mattermost Operational Backend Integration: **accepted / closed** (`96a5249`).

PHASE 27B-C — Mattermost Flutter UX + matched-version E2E prep: **accepted / closed** (part of 27B closure).

PHASE 27C-R1 — Explicit Intake foundation + one Google Drive object: **implementation complete, awaiting architect review**.

Do **not** merge, deploy to production `main`, or start Yandex Disk / Flutter paste-drop until 27C-R1 review.

## Superseded experiments (do not merge / deploy)

Previous technical branches treated as superseded after product-intent clarification:

- `review/phase-27c-google-drive` (27C-A full-drive metadata sync)
- `review/phase-27c-google-drive-ops` (27C-B recurring Drive sync / scheduler)

They implemented whole-drive crawl, not explicit user-selected resources.

## PHASE 27C-R1 delivered

- Shared `POST /intake/link` explicit-link intake contract
- Google Drive URL parser (known hosts only; ID extraction; no arbitrary HTTP fetch)
- Single-resource Drive metadata lookup (`GET /drive/v3/files/{id}` only)
- Google OAuth `drive.readonly` scope + `drive_available` connection snapshot
- Canonical `google_drive` Object upsert with idempotency
- Trusted OpenTarget for `google_drive` file/folder
- Focused backend tests

## Product model (explicit intake)

```text
user explicitly pastes/drops/selects one resource
→ Secretary resolves exactly that resource
→ creates/refreshes exactly one Inbox Object
→ later bounded content extraction/summarization (not in 27C-R1)
```

Cloud/local file sources are explicit-intake resources. Secretary does not crawl an entire cloud drive merely because an account is connected.

## Not in 27C-R1

- Yandex Disk explicit intake
- Flutter paste/drop UX
- Drive content download / export / summarization
- Full-drive sync, `drive_sync_state`, migration `0020`, recurring `sync_google_drive`
- Production deploy

## Roadmap — PHASE 27 Source Completion

- **27A** — accepted (`f92ca0c`)
- **27B** Mattermost — accepted (`1dc493d`)
- **27C-R1** Explicit Intake + Google Drive link — awaiting review
- **27C-R2+** Yandex Disk link, Flutter paste/drop, local explicit intake alignment — not started

Safe External Actions follow Source Completion.
