# Project state

## Current phase

PHASE 22 — Search and Assistant UI: **implemented, awaiting review**

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **accepted / closed**

PHASE 23 — voice: **not started**

PHASE 20 — Flutter client: **accepted / closed**

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–21: (prior phases, PHASE 21 closed)
- PHASE 22 (awaiting review):
  - `GET /search` reused by Flutter Search screen (user-scoped, optional kind filter)
  - `POST /assistant/message` with bounded message/history, optional `context_object_id` / `context_notification_id`
  - Reuses Secretary agent: Responses API `store=False`, bounded tool loop, `DomainToolService` / `ContextService`
  - Short-lived DB sessions per tool call; no open transaction across OpenAI calls
  - Flutter Search + Assistant chat screens; Object Detail **Ask Secretary** handoff; optional Inbox notification context
  - Backend `test_assistant.py`; client search/assistant tests
  - `pytest` 385+ passed (2 pre-existing unrelated failures in auth_capture/provenance on shared DB)
  - `flutter analyze`, `flutter test`, `flutter build apk --debug` verified

## Not done

- PHASE 23 voice
- Graph editor
- Persistent assistant chat database

## Next phase

PHASE 22 review. Do not start PHASE 23 until PHASE 22 is accepted.
