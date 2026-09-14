# Current task — Voice Assistant A R2-R1

## Status

**Voice Assistant A R2-R1: implemented / awaiting Architect review** on `review/voice-assistant-a`.

Application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Parent SHA: `44161b01b8b065204de0f5025fc55b96910f6058`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

Overall Voice Assistant A is still **NOT CODE ACCEPTED**. Not deployed. Do not start Voice B. Do not deploy.

R1 review: **PASS**. R2 marker architecture/semantics: **PASS**.

## Inherited accepted phases

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED**

Application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

**Teams A remains: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**.

## R2-R1 delivered

Tiny reference hygiene for `list_inbox_since_review_marker`:

- `collect_object_ids_from_bounded_tool` adds only `items[].object_id` (canonical visible order). `anchor_object_id` is **not** a candidate/reference.
- `collect_seen_object_ids_from_bounded_tool` still includes `anchor_object_id` plus item IDs, so the model-visible anchor remains a legal `set_inbox_review_marker` target.

No change to marker semantics, payload, query, permissions, MCP, mutation, or Flutter.

## Verification (Executor)

- Ruff on touched files: PASS
- `tests/test_inbox_review_marker_assistant.py` + evidence/provenance + gateway + ANNOTATE policy + Inbox REST marker: 108 passed
- Client rebuild: not required (backend-only)

## Stop

Wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED. Do not start Voice B.
