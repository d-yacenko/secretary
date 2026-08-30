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

PHASE 23D-C — Deploy & Manual Agent E2E Checkpoint: **deployed / ready for manual testing**

Evidence: `docs/phase_23d_c_manual_e2e.md` (manual scenarios A–H **not yet run**).

## VDS production

- Host: `185.233.107.66` (`web-itx.duckdns.org`)
- Path: `/opt/secretary`
- SHA: `b30b95e152656fbbec3e7a3028216ae05ad35659`
- Deployed: 2026-08-30
- Checkout: `main`, clean (no tracked modifications)
- Alembic current/head: `0018` (`pending_action_plans`)
- Health: `{"status":"ok"}` at `http://127.0.0.1:18080/health`
- API: `http://127.0.0.1:18080` on VDS host (localhost only; not on public interface)
- Update: `cd /opt/secretary && git pull && cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`

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
