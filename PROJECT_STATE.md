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

PHASE 23D-B — Approval UX & Safe Agent Resume: **closure corrective, awaiting acceptance**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- **Accepted backend/transcription work (`94f04ef` / `43de268`) deployment pending** — VDS SSH credentials unavailable from dev environment
- **PHASE 23B client accepted on `main` (`e339e2e`) — not deployed**
- **PHASE 23C accepted on `main` (`7165b7f`) — not deployed**
- **PHASE 23D-A accepted on `main` (`fa24217`) — not deployed**
- **PHASE 23D-B not deployed** — on `review/phase-23d-b`

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
- PHASE 23D-A (awaiting review on `review/phase-23d-a`):
  - Interactive Assistant `INTERNAL_WRITE` requires approval (`ExecutionContext.INTERACTIVE_ASSISTANT`)
  - `pending_action_plans` table with frozen validated actions
  - `POST /assistant/action-plans/{id}/approve` and `/reject` execute exact stored arguments
  - Assistant `/assistant/message` returns optional `pending_action_plan`

## Next phase

PHASE 23D-B — approval UX and conversational post-approval resume (not started).
