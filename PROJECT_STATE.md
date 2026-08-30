# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **accepted / closed** (`a1bcb90`)

PHASE 22.7 — Assistant Cost & Latency Optimization: **accepted / closed** (`94f04ef`)

PHASE 23A — Voice Transcription Foundation: **accepted / closed** (`43de268`)

PHASE 23B — Flutter push-to-talk: **accepted / closed** (`e339e2e`)

PHASE 23C — Agent Execution Gateway & Tool Policy: **implemented, awaiting review**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- **Accepted backend/transcription work (`94f04ef` / `43de268`) deployment pending** — VDS SSH credentials unavailable from dev environment
- **PHASE 23B client accepted on `main` (`e339e2e`) — not deployed**
- **PHASE 23C not deployed** — on `review/phase-23c`

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
- PHASE 23C (awaiting review on `review/phase-23c`):
  - Canonical tool registry with permission classes
  - `ToolExecutionGateway` between Assistant tool calls and `DomainToolService`
  - Baseline policy: READ/INTERNAL_WRITE/EXTERNAL_PROPOSE allow; EXTERNAL_WRITE/COMMUNICATE require approval (no persistence yet)

## Next phase

PHASE 23D — persisted action plans and interactive approval (not started).
