# Current task — PHASE 28B-C awaiting architect review

## Status

PHASE 28B-A — Per-User Background AI Runtime: **accepted / closed** at `2ab6c8d96c5c5695a57042e9e487194f1a6515d3`. Deployment: **PASS**.

PHASE 28B-B — Per-User Transcription Credential: **accepted / closed** at `18c7bb1f8fd708c7c121217b62071ba26adada38`. Deployment: **PASS**.

PHASE 28B-C — Per-User Request-Time Graph Embeddings: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start 28C until review.

## PHASE 28B-C delivered

- `POST /objects` and `PATCH /objects/{id}` resolve OpenAI credential per user via `resolve_openai_api_key`
- Read-only graph routes do not resolve OpenAI credentials
- Broken personal credential → HTTP 502 on mutations; reads remain usable
- `OPENAI_EMBEDDING_MODEL` remains deployment-level

## Branch

`review/phase-28b-graph-embeddings` from `18c7bb1f8fd708c7c121217b62071ba26adada38`.

## Not in 28B-C

- Source sync preferences (28C)
- Task mutation embedding path (`tasks.py` still deployment-global)
- Flutter changes
