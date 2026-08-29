# Project state

## Current phase

PHASE 22 — Search and Assistant UI: **accepted / closed**

PHASE 23 — voice: **not started**

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **accepted / closed**

PHASE 20 — Flutter client: **accepted / closed**

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–21: (prior phases, PHASE 21 closed)
- PHASE 22 (closed):
  - `GET /search` reused by Flutter Search screen (user-scoped, optional kind filter)
  - `POST /assistant/message` with bounded message/history, optional `context_object_id` / `context_notification_id`
  - Reuses Secretary agent: Responses API `store=False`, bounded tool loop, `DomainToolService` / `ContextService`
  - Per-turn tool-call budget (`DEFAULT_MAX_TOOL_CALLS = 5`) across all Responses rounds
  - Short-lived DB session per tool call: commit on success, rollback on failure
  - Assistant writes defer synchronous embedding; enqueue `embed_object` after graph mutation
  - Assistant tool execution bounds (search/list/neighbors ≤20, context ≤8000 chars) with SQL-limited neighbors
  - Bounded model tool JSON; references from bounded view only (`MAX_ASSISTANT_REFERENCES = 20`)
  - Fail-closed canonical URI sanitizer (no query/fragment) for model output and `AssistantReferenceOut`
  - Assistant `get_context(object_id, max_chars)` only — no query param in OpenAI tool schema
  - UI context as delimited evidence (not system instructions)
  - Flutter Search + Assistant chat; `affected_objects` rendered as proposed changes
  - Backend `test_assistant.py`; client search/assistant tests
  - `pytest` 409 passed; `ruff check .` passes
  - `flutter analyze`, `flutter test`, `flutter build apk --debug` verified
  - VDS deployed at `1f9be4c` (Alembic `0015`); live health/search → 200
  - VDS assistant smoke: **blocked** — `OPENAI_API_KEY` not present in `/opt/secretary/.env` or container env (`POST /assistant/message` → 500); no non-empty OpenAI-backed answer observed

## Not done

- PHASE 23 voice
- Graph editor
- Persistent assistant chat database
- VDS OpenAI credential for live Assistant smoke (add `OPENAI_API_KEY` to `/opt/secretary/.env` and recreate api/worker; do not commit)

## Next phase

PHASE 23 — voice (not started).
