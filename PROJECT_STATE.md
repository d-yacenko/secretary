# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **accepted / closed** (`a1bcb90`)

PHASE 22.7 — Assistant Cost & Latency Optimization: **accepted / closed** (`94f04ef`)

PHASE 23A — Voice Transcription Foundation: **accepted / closed** (`43de268`)

PHASE 23B — Flutter push-to-talk: **accepted / closed** (`e339e2e`)

PHASE 23C — Agent Execution Gateway & Tool Policy: **accepted / closed** (`7165b7f`)

PHASE 23D-A — Frozen Pending Action Plans: **accepted / closed** (`fa24217`)

PHASE 23D-B — Approval UX & Safe Agent Resume: **accepted / closed** (`b30b95e`)

PHASE 23D-C — Deploy & Manual Agent E2E Checkpoint: **manual core Agent E2E completed**; core Agent flow PASS; findings in PHASE 23D-D

Evidence: `docs/phase_23d_c_manual_e2e.md`

PHASE 23D-D — MVP Interaction Closure: **accepted / closed** (`eb433a6`)

PHASE 23E — Unified Permission Gateway & Agent Task Lifecycle: **accepted / closed** (`402c234`)

PHASE 24 — Graph Workspace & Direct Task Management: **accepted / closed** (`e128f26`).

PHASE 24 post-deploy E2E corrective: **accepted / closed** (`684233b`).

PHASE 24 final matched-version manual Graph E2E: **functionally PASS** (2026-08-30).

PHASE 25 — Russian-first UI & Graph Mobile Polish: **accepted / closed** (`143f674`).

PHASE 25 manual UI verification: **PASS** (2026-08-30).

PHASE 25.1 — UX Baseline: **accepted / closed** (`4c40b93`).

PHASE 26A — Personal Data Correlation Core & Semantic Resource Context: **accepted / closed** (`1e41198`).

PHASE 26B — Source Navigation, Attachments & Client-assisted File Intake: **accepted / closed** (`be6bdfa`).

PHASE 26 — Personal Data Correlation: **accepted / closed** (`5c4ffc40`).

PHASE 26C — Structured Query, Search UX & Topology-Aware Graph: **accepted / closed** (`5c4ffc40`).

PHASE 26C manual matched-version Linux E2E: **PASS** (2026-08-31).

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — Live Source Sync, Inbox/Today & Assistant Presentation: **accepted / closed** (`f92ca0c`).

PHASE 27B — Mattermost Read-Only Source Connector: **accepted / closed** (`1dc493d`).

PHASE 27B-A — Mattermost Secure Connector & Sync Core: **accepted / closed** (`87b16cb`).

PHASE 27B-B — Mattermost Operational Backend Integration: **accepted / closed** (`96a5249`).

PHASE 27B-C — Mattermost Flutter UX + matched-version E2E prep: **accepted / closed** (part of 27B closure).

PHASE 27C-R1 — Explicit Intake foundation + one Google Drive object: **accepted / closed** (`467332c`). Google Drive 403 corrective closed in PHASE 27C-R4C.

PHASE 27C-R2 — Yandex Disk explicit share-link intake: **accepted / closed** (`374db8aa4bf4b05e922812414e723c7f8a2c4731`).

PHASE 27C-R3 — Local explicit file/folder semantics: **accepted / closed** (`8d64f2cd907bb02f2edc1c223bba93185324d5d0`).

PHASE 27C-R4A — Inbox Explicit Intake UI: **accepted / closed** (`70117058ce6472f2d1e3d11015a09137f8a2d047`).

PHASE 27C — Yandex Account UX corrective: **accepted / closed** (`70117058ce6472f2d1e3d11015a09137f8a2d047`).

PHASE 27C-R4C — Google Drive explicit-intake 403 corrective: **accepted / closed** (`765f79126329a26f42180d00a32fb646c6ec1598`). Deployment and real Google Drive/Sheets explicit-link E2E: **PASS**.

PHASE 28A — User Profile & Per-User Settings Foundation: **accepted / closed** (`d9a7ea874379366fcacdb0646efcad871764658c`). Matched-version manual E2E: **PASS**.

PHASE 28B-A — Per-User Background AI Runtime: **accepted / closed** (`2ab6c8d96c5c5695a57042e9e487194f1a6515d3`). Deployment: **PASS**.

PHASE 28B-B — Per-User Transcription Credential: **implementation complete, awaiting architect review**.

Architect context refresh checkpoint: **completed** at `bc5a7d29976482bca033543c49a04f9b51f974d0`.

Next: **architect review of PHASE 28B-B** on branch `review/phase-28b-transcription`.

Safe External Actions follow Source Completion (PHASE 27C explicit intake track).

## PHASE 27B-A verification (accepted at `87b16cb`)

- Alembic head: `0019`
- Mattermost connect + bounded read-only sync core; fake-transport tests
- Scheduler / `/sources/status` / operational integration deferred to 27B-B

## PHASE 27B-B verification (accepted at `96a5249`)

- Recurring `sync_mattermost` job wired into PHASE 27A lifecycle (scheduler, worker, manual sync, status, connections, OpenTarget)
- Alembic head remains `0019` (no new migration)
- Focused tests: `test_phase_27b_operational.py` + PHASE 27A regression
- No Flutter / deploy in this subphase

## PHASE 27B-C verification (accepted as part of 27B closure at `1dc493d`)

- Flutter Mattermost connect UX on Account → Подключения; typed API models; provider `M` / Mattermost
- Connect ensures recurring `sync_mattermost` row runnable immediately (no inline message sync on HTTP connect)
- Matched-version manual E2E completed; production deploy deferred until broader release policy

## PHASE 27C-R1 verification (accepted at `467332c`)

- Shared `POST /intake/link` explicit-link intake API
- Google Drive: URL parser, single-file metadata lookup, Object upsert, OpenTarget
- OAuth `drive.readonly` scope; `drive_available` in connection snapshot
- No full-drive sync, no migration beyond Alembic `0019`
- Superseded experiments `review/phase-27c-google-drive` and `review/phase-27c-google-drive-ops` — not for merge/deploy

## PHASE 27C-R2 verification (accepted at `374db8aa4bf4b05e922812414e723c7f8a2c4731`)

- Yandex Disk public/share links via same `POST /intake/link`
- Provider dispatch by URL host; fixed `cloud-api.yandex.net` public resources API only
- Folder share URL → one folder Object; no `_embedded` child import
- OpenTarget with re-validated Yandex share URLs only
- No Yandex Disk OAuth, no migration beyond `0019`

## PHASE 27C-R3 verification (accepted at `8d64f2cd907bb02f2edc1c223bba93185324d5d0`)

- `POST /local/folders/client-intake` — explicit local folder → one folder Object
- No bounded walk / child import on explicit folder path; single-file client intake preserved
- `folder` in `RECENT_SOURCE_KINDS`; local folder OpenTarget via `client_source_path`
- Flutter folder pick/drop aligned; no indexing-policy dialog
- Preserves device display name and existing root policy on repeat intake
- No migration beyond Alembic `0019`

## PHASE 28A verification (awaiting architect review)

- Migration `0020_user_settings`: `user_settings`, `user_openai_credentials`; Alembic head `0020`
- `EffectiveUserSettingsService` + encrypted per-user OpenAI credential (`SECRETARY_CREDENTIAL_KEY`)
- APIs: `GET/PATCH /me`, `GET/PATCH /me/settings`, `PUT/DELETE /me/credentials/openai`
- Assistant `POST /assistant/message` uses effective per-user AI settings/key
- Account UI: **Профиль** / **ИИ** / **Подключения**; local intake controls removed from Account only
- `ruff check` on changed backend files: PASS
- `pytest`: 965 passed, 3 skipped
- `flutter test test/account/`: 32 passed
- `flutter test test/inbox/inbox_explicit_intake_test.dart`: 14 passed
- `flutter analyze`: 0 errors (pre-existing warnings)

## PHASE 27C-R4A verification (accepted at `70117058ce6472f2d1e3d11015a09137f8a2d047`)

- Inbox intake bar: cloud link paste + Add; local file/folder icon buttons
- `SecretaryApiClient.intakeLink()`; explicit intake refreshes Inbox without `/sources/sync`
- Linux local drag/drop via `DropTarget`; browser cloud-link drag/drop deferred to R4B
- Flutter widget tests: `test/inbox/inbox_explicit_intake_test.dart`
- No migration beyond Alembic `0019`

## PHASE 26C verification (accepted)

- full `ruff check .`: 49 known pre-existing findings (exit 1), 0 new PHASE 26C findings
- `pytest`: 779 passed, 3 skipped
- `flutter analyze`: 49 info/warning, 0 errors
- `flutter test`: 266 passed
- Android APK: PASS
- Linux build: PASS
- Android `minSdk`: 23
- migrations: none

## PHASE 26A verification (accepted)

- full `ruff check .`: 50 known pre-existing findings, none introduced by closure
- `pytest`: 693 passed, 3 skipped
- `flutter analyze`: 23 info/warning, 0 errors
- `flutter test`: 218 passed
- Android APK: PASS
- Linux build: PASS
- Android `minSdk`: 23
- migrations: none

## PHASE 26B verification (accepted)

- full `ruff check .`: 51 existing findings, exit 1
- `pytest`: 733 passed, 3 skipped
- `flutter analyze`: 48 info/warning, 0 errors
- `flutter test`: 249 passed
- Android APK: PASS
- Linux build: PASS
- Android `minSdk`: 23
- migrations: none
- final focused Ruff: PASS
- final focused pytest: 30 passed

## PHASE 26B accepted decisions

- Local-device mechanical extraction happens client-side where practical
- Semantic understanding remains backend-side
- Local raw files are not uploaded by default
- `.txt` / `.md` / `.csv` are client-indexable
- Unsupported formats (PDF, DOCX, XLSX, PPTX, Parquet, images, archives) are metadata-only for client-assisted intake
- Metadata-only downgrade removes old indexed content
- Gmail / Yandex attachments are canonical file objects
- `open-target` is the canonical source-navigation abstraction
- Local open actions are device-aware
- Android persistent local reopen remains deferred
- Yandex Mail uses truthful mailbox-level fallback when exact deep link cannot be derived

## PHASE 26B architecture (implemented)

Mechanical local-file extraction may happen on Desktop/Android client.

Client: file selection/drop → filename/path/size/mtime/hash → bounded text/chunks → bounded dataset schema/sample/statistics → typed bounded payload.

Backend: validation → canonical Object/Representation → semantic summary → embedding → correlation.

Semantic understanding remains server-side. See also `DECISIONS.md`.

## Deferred UX / data backlog (not PHASE 25.1)

### PHASE 26 — Personal Data Correlation

Semantic file summaries; folders as retrieval/graph source; local-file and email-attachment objects; open-in-source/file/folder actions; Gmail/Yandex deep links; desktop drag-and-drop; Android file picker; email attachments; proper search sorting; topology-aware Graph layout; curved/routed edges.

### PHASE 29 — Personal Workflow Intelligence

Unified colored labels/tags (Работа, Учёба, Наука, Личное, Дом, Финансы, Здоровье, Отдых, Идеи) — one canonical label system.

### PHASE 30 — Release / advanced UX

Manual Graph node drag; persisted personal Graph layout; final desktop/mobile polish.

## VDS production

- Host: `185.233.107.66` (`web-itx.duckdns.org`)
- Path: `/opt/secretary`
- SHA: `f472b8ce51b4f63cf85c81affe0f40cd9e0b7a66`
- Deployed: 2026-08-31 (PHASE 26 closure — full PHASE 26 accepted)
- Accepted application: `5c4ffc40fd7462c1ecc29b2a00bc9f5920a50ba6`
- Checkout: `main`, clean (no tracked modifications)
- Alembic current/head: `0018` (`pending_action_plans`)
- Health: `{"status":"ok"}` at `http://127.0.0.1:18080/health`
- API internal: `http://127.0.0.1:18080` on VDS host (localhost only)
- API public HTTPS: `https://web-itx.duckdns.org/secretary`
- Update: `cd /opt/secretary && git pull && cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`

### PHASE 24 deployment note

The first manual Graph/Delete failures (`{"detail":"Not Found"}`) occurred because the PHASE 24 Flutter client called routes that did not exist on the PHASE 23D-B VDS backend (`b30b95e`). After deploying `e128f26`, `GET /graph/workspace`, rooted graph, and `DELETE /tasks/{id}` return typed domain responses (not generic FastAPI route 404).

## PHASE 25.1 verification (accepted)

- `flutter analyze`: 21 info/warning, 0 errors
- `flutter test`: 213 passed
- `flutter build apk --debug`: PASS
- `flutter build linux`: PASS
- backend focused tests: 1 passed
- Android `minSdk`: 23

## PHASE 25 verification (accepted)

- `flutter analyze`: 23 info/warning, no new errors
- `flutter test`: 187 passed
- `flutter build apk --debug`: PASS
- `flutter build linux`: PASS
- Android `minSdk`: 23

## PHASE 22.7 baseline note

VDS `assistant_turn` logs were not available from the local development environment during implementation. Baseline token/tool-call metrics from the recent testing period could not be recorded here. Continue measuring cost via extended `assistant_turn` telemetry after deploy.

## Working components

- PHASE 22.6 (closed at `a1bcb90`)
- PHASE 22.7 (closed at `94f04ef`)
- PHASE 23A (closed at `43de268`):
  - `POST /assistant/transcribe` bounded multipart upload (`audio` field, 10 MiB max)
  - `OPENAI_TRANSCRIPTION_MODEL` (default `gpt-4o-mini-transcribe`)
  - OpenAI + fake transcription providers; no audio persistence
  - `assistant_transcription` telemetry (no transcript/audio logging)
- PHASE 23B (closed at `e339e2e`):
  - Flutter Assistant microphone → temp WAV → `/assistant/transcribe` → `sendMessage(transcript)`
  - Race-safe voice lifecycle; `record 5.2.1` + `minSdk 23`
- PHASE 23C (closed at `7165b7f`):
  - Canonical tool registry with permission classes
  - `ToolExecutionGateway` between Assistant tool calls and `DomainToolService`
  - Baseline policy: READ/INTERNAL_WRITE/EXTERNAL_PROPOSE allow; EXTERNAL_WRITE/COMMUNICATE require approval (no persistence yet)
- PHASE 23D-A (closed at `fa24217`):
  - Interactive Assistant `INTERNAL_WRITE` requires approval (`ExecutionContext.INTERACTIVE_ASSISTANT`)
  - `pending_action_plans` table with frozen validated actions
  - `POST /assistant/action-plans/{id}/approve` and `/reject` execute exact stored arguments
  - Assistant `/assistant/message` returns optional `pending_action_plan`
- PHASE 23D-B (closed at `b30b95e`):
  - Approval UX, safe resume, recoverable approve/reject errors
  - Terminal action plan history events for LLM continuity (23D-D)
- PHASE 23D-C (manual E2E completed):
  - Deployed backend at `b30b95e`; HTTPS proxy `https://web-itx.duckdns.org/secretary`
  - Core Agent loop PASS; voice/mobile UX findings addressed in 23D-D
- PHASE 25 (closed at `143f674`):
  - Russian-first Flutter UI (`ru_RU`), domain label mapper, Graph node overflow fix
  - Notification presentation labels; real-widget Graph overflow regression tests
- PHASE 26A (closed at `1e41198`):
  - Bounded correlation pipeline (`summarize_resource` → `embed_object` → `correlate_object`)
  - Deterministic email/thread relations; `CorrelationJudge`; proposed relation review API
  - Semantic summaries; folder objects + `contains`; folder-scoped context retrieval
  - Graph proposed-relation UI (Предложено / Подтвердить / Отклонить)
- PHASE 26B (closed at `be6bdfa`):
  - Client-assisted mechanical extraction (`.txt`, `.md`, `.csv`) with bounded representations
  - Metadata-only registration for unsupported formats; `POST /local/files/client-intake`
  - `GET /objects/{id}/open-target` source navigation resolver
  - Gmail / Yandex Mail attachment objects + `email --contains--> attachment`
  - Flutter: device identity, file/folder picker, Linux drag-and-drop, source actions, email attachments UI
  - Assistant/Capture context via object IDs (no raw file upload by default)

## Next phase

PHASE 26C — Graph Topology & Search Ordering. **ARCHITECT CONTEXT REFRESH CHECKPOINT** before start. Do not implement until architect context refresh is complete.
