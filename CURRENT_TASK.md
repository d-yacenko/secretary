# Current task — Unified Conversation & Inbox Compaction A

## Status

Unified Conversation & Inbox Compaction A is **implemented / awaiting Architect review**.
It is **NOT CODE ACCEPTED**. It is **NOT PRODUCTION ACCEPTED**. **NOT DEPLOYED**.

Canonical base / docs tip at phase start: `54b820d01d97c1ae44fba3d2d5831e1605e9c5d7`.
Exact deployed application runtime tree remains: `7610cc1c6ce24764fae73317a6925cdce7bd27b2`.
Production remains `7610cc1c6ce24764fae73317a6925cdce7bd27b2`, Alembic **0041**.
Migration: **NONE**.

Voice B is not started. Graph Refinement A is not started.
Do not mark Voice Assistant A PRODUCTION ACCEPTED.

## Voice Assistant A factual carry-forward (do not reopen Voice A code)

- Canonical hands-free complete Inbox review was physically re-tested after R2.
- Full review of the current 4-object window completed.
- `POST /inbox/review-marker/complete` returned 200.
- Marker advanced to the frozen top.
- Canonical Inbox marker completion gate is **PASS**.
- Wording variants such as «озвучь новые сообщения» may still lead to different tool behavior in edge cases; the user accepts current behavior for now.
- Real Teams inbound webhook proof remains deferred until a natural incoming Teams message is available.
- Voice A therefore remains **deployed / not formally PRODUCTION ACCEPTED**.

## This phase (Compaction A)

Turn the flat communication-heavy Inbox into a unified conversation view **without changing source acquisition**.

- Conversation Stack is **presentation**, not a domain Object and not a graph identity.
- Underlying messages remain first-class atomic Secretary Objects.
- Optional `conversation_groups` overlay on `/inbox` and `/inbox/feed`; `recent_source_objects` and feed cursor unchanged.
- Burst gap: **15 minutes** between adjacent messages.
- False merge is worse than split.
- Marker is defined only by underlying Object/`feed_at` tuples; a stack that would hide the marker is split.
- Semantic summaries are derived `Representation(kind=conversation_stack_summary)`, fingerprint-bound, async via existing job/LLM/Cost Guard.
- Telegram transport/group acquisition is deferred; source acquisition is unchanged.
- Graph Refinement remains the next heavy phase after this work.
