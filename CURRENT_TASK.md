# Current task — Voice Assistant A R2

## Status

**Voice Assistant A R2: implemented / awaiting Architect review** on `review/voice-assistant-a`.

Application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

Parent SHA: `bbcef9a109f8c6ce73048cd87e8e5b3adfaa41d2`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

Canonical base: `54f14a86b4c6de3c29b2f14c8a8a14b4db5ddf8c`

Inherited accepted application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

Overall Voice Assistant A is still **NOT CODE ACCEPTED**. Not deployed. Do not start Voice B. Do not deploy.

R1 review: **PASS** at application SHA `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`.

## Inherited accepted phases

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED**

Application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

**Teams A remains: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**. The Teams external blocker does not block Voice Assistant A.

## R2 delivered

Provider-neutral Secretary Inbox review-marker tools on the ordinary Assistant path (typed and voice). No second voice orchestrator. No Flutter phrase parser. No provider read/unread write. No migration.

- `list_inbox_since_review_marker` — READ. Bounded snapshot of Inbox-eligible objects **strictly newer** than `(anchor_feed_at, anchor_object_id)`. Anchor itself is not new. No marker → explicit `marker_not_set`; historical Inbox is not classified as unread/new.
- `set_inbox_review_marker` — ANNOTATE. `after_object_id` required; must have been exposed this Assistant turn. Immediate; no Pending Action Plan; no external write. Same ownership/inbox-eligibility as `InboxReviewMarkerService`.
- `clear_inbox_review_marker` — ANNOTATE. No input. Immediate; no Pending Action Plan.

Canonical ordering reuses `feed_at DESC, id DESC` via `RecentSourceService.list_strictly_newer_than`. Visual Inbox +1 is accounted for: the UI line is after the inclusive anchor; if the newest object is the anchor, Assistant reports zero new items.

Marker mutation requires explicit user intent. Fetching, summarizing, generating text, or requesting TTS does **not** move the marker.

MCP: tools are registry-exposed; ANNOTATE remains fail-closed (`REQUIRE_APPROVAL`). Not added to `PROACTIVE_READ_TOOL_NAMES`.

## Verification (Executor)

- Backend ruff on R2 files: PASS
- `tests/test_inbox_review_marker_assistant.py` + Inbox REST marker + tool gateway/contracts + ANNOTATE policy + speech/transcription: 113 passed
- Additional MCP / evidence / Inbox chronology / labels-a: green except pre-existing unrelated `test_assistant_tool_path_kind_all_finds_xlsx` (retrieve/xlsx; not R2)
- Client Voice A + Assistant + Inbox workflow: 120 passed
- Android `minSdk` remains 23
- Migrations: **NONE**
- `ai_traces_user_id_fkey` baseline not repaired and not re-run in R2 (R2 does not change AI-trace user_id handling)

## Stop

Wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED. Do not start Voice B.
