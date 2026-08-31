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

PHASE 26A closure corrective delivered on branch `review/phase-26a-correlation-core` (hardening correlation validation, candidate caps, metadata-only embed pipeline, semantic-summary revision safety, folder-scoped context, RFC Message-ID handling, relation decision API tests, Flutter regressions).

Next planned subphase: PHASE 26B — Source Navigation, Attachments & Client-assisted File Intake.

Do not start PHASE 26B until PHASE 26A architect review is recorded.

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
- SHA: (updated after PHASE 25.1 deploy)
- Deployed: 2026-08-30 (PHASE 25.1 UX Baseline)
- Accepted application: `4c40b93a59e33b62ec13a2770b31b322eac2cc94`
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

## Next phase

PHASE 26B — Source Navigation, Attachments & File Intake. Do not start until PHASE 26A architect review is recorded.
