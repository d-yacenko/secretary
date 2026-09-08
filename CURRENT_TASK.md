# Current task — Workflow Intelligence Pass D-R3

## Status

Workflow Intelligence Pass D-R3: **implementation complete**; **awaiting Architect review**.

Do **not** deploy this corrective before Architect acceptance.
Do **not** start Pass E.

## Branch

`review/workflow-intelligence-auto-label-d`

## Production truth

- Production application SHA: `e621f4cbb7d9d4531686d79b301f4d8c3b1b8e28` (Pass D-R2, Architect-accepted application)
- Alembic on production: **`0032`** (deployed)
- `auto_label_enabled=false` in production (must remain OFF)
- Pass D application accepted; production E2E/closure **BLOCKED** by D-R3 (post-model audit / `users FOR UPDATE` hang)
- Production no-backfill / default / opt-out checks: **PASS**
- Production assignment happy path: **NOT PASS**
- Pass E: not started

## Parent / base

`e621f4cbb7d9d4531686d79b301f4d8c3b1b8e28`

## Scope

Keep the Pass D product contract. No new autonomy, no Proactive changes, no taxonomy automation, no AI-audit schema/FK redesign.

- User serialization sentinel: PostgreSQL `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`, `populate_existing=True`) in `acquire_auto_label_user_gate` and `LabelService._lock_user`
- Keep `UserSettings FOR UPDATE` and source Object / vocabulary `FOR UPDATE` for the R2 mutation fence
- Real separate-session AI-audit regression (do not patch `ai_trace_session` to `nullcontext`; do not redirect audit `SessionLocal` to the worker session)

## Non-goals

Do not deploy production. Do not enable auto-labeling in production.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
