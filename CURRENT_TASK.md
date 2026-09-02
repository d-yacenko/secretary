# Current task — PHASE 28B-C2 awaiting architect review

## Status

PHASE 28B-A — Per-User Background AI Runtime: **accepted / closed** at `2ab6c8d96c5c5695a57042e9e487194f1a6515d3`. Deployment: **PASS**.

PHASE 28B-B — Per-User Transcription Credential: **accepted / closed** at `18c7bb1f8fd708c7c121217b62071ba26adada38`. Deployment: **PASS**.

PHASE 28B-C — Per-User Request-Time Graph Embeddings: **accepted / closed** (code) at `485e24942fb778e1952153394dccac552f9e88c3`. Deployment: **pending** combined 28B deployment after C2 review.

PHASE 28B-C2 — Remaining Per-User Request-Time / Tool Embeddings: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start 28B-D / 28C until review.

## PHASE 28B-C2 delivered

- Direct task PATCH (title/body) uses per-user embedding credential
- Status/delete/due_at-only PATCH skip credential resolution
- Interactive Assistant tool session uses per-user credential
- MCP authenticated tool session uses per-user credential
- Action plan approval uses deferred writes without embedding provider

## Branch

`review/phase-28b-remaining-embeddings` from `485e24942fb778e1952153394dccac552f9e88c3`.

## Approved next after full 28B closure

PHASE 28B-D — Source Status Diagnostics & UI Freshness (not started).

## Not in 28B-C2

- Source sync preferences (28C)
- Flutter changes
- SecretaryService legacy migration
