# Project state

## Current phase

PHASE 22 — Search and Assistant UI: **final corrective implemented, awaiting final acceptance**

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **accepted / closed**

PHASE 23 — voice: **not started**

PHASE 20 — Flutter client: **accepted / closed**

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–21: (prior phases, PHASE 21 closed)
- PHASE 22 (awaiting final acceptance):
  - `GET /search` reused by Flutter Search screen (user-scoped, optional kind filter)
  - `POST /assistant/message` with bounded message/history, optional `context_object_id` / `context_notification_id`
  - Reuses Secretary agent: Responses API `store=False`, bounded tool loop, `DomainToolService` / `ContextService`
  - Per-turn tool-call budget (`DEFAULT_MAX_TOOL_CALLS = 5`) across all Responses rounds
  - Short-lived DB session per tool call: commit on success, rollback on failure
  - Assistant writes defer synchronous embedding; enqueue `embed_object` after graph mutation
  - Bounded tool outputs for model input; UI context as delimited evidence (not system instructions)
  - Flutter Search + Assistant chat; `affected_objects` rendered as proposed changes
  - Backend `test_assistant.py`; client search/assistant tests
  - `pytest` 393 passed; `ruff check .` passes
  - `flutter analyze`, `flutter test`, `flutter build apk --debug` verified

## Not done

- PHASE 23 voice
- Graph editor
- Persistent assistant chat database
- VDS deploy for PHASE 22 final corrective (explicitly deferred)

## Next phase

PHASE 22 final acceptance. Do not start PHASE 23 until PHASE 22 is accepted.
