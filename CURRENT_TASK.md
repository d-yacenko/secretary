# Current task — PHASE 28B-B awaiting architect review

## Status

PHASE 28B-A — Per-User Background AI Runtime: **accepted / closed** at `2ab6c8d96c5c5695a57042e9e487194f1a6515d3`. Deployment: **PASS**.

PHASE 28B-B — Per-User Transcription Credential: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start 28C until review.

## PHASE 28B-B delivered

- `POST /assistant/transcribe` resolves OpenAI credential per authenticated user via `resolve_openai_api_key`
- Transcription model remains deployment-level (`OPENAI_TRANSCRIPTION_MODEL`)
- Broken personal credential → HTTP 502 generic (not Secretary 401)
- No `get_effective_settings()` on transcription path

## Branch

`review/phase-28b-transcription` from `2ab6c8d96c5c5695a57042e9e487194f1a6515d3`.

## Not in 28B-B

- Source sync preferences (28C)
- Flutter microphone UX changes
- Background embed/summarize/correlate changes
