# Current task — Scheduled Work A

## Status

**Scheduled Work A: CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**

Branch: `review/scheduled-work-a`
Exact production application SHA: `76721b16650c49ce32b6405e8a001bdc6822bec4`
Production Alembic: **0038 / 0038**
Migration: **0038 → 0037** (`objects.planned_start_at`, `objects.planned_end_at`)
Docs-only closure parent: `90b8e3298d6ff6215eaad1fbce48f1c0fe8ccc51`
No docs-only deploy.

## Contract

Scheduled work is an explicit user-planned task execution interval on `Object` (`planned_start_at` / `planned_end_at`). It is not `due_at`, not a calendar event, not hard busy time, and does not write Google/Yandex calendars.

Week layers: confirmed calendar events = HARD; `scheduled_work` = SOFT; `temporal_hints` = TENTATIVE.

Week `scheduled_work` is fail-closed: `open` / `in_progress` / `done` only. NULL, legacy `completed`, cancelled, archived, deleted, and unknown statuses are excluded.

Schema: both planned fields NULL, or `kind=task` and both non-NULL and `planned_end_at > planned_start_at`. No backfill.

## Production acceptance

Upgrade **0037 → 0038** succeeded. `/health` healthy. No schema backfill; existing tasks stayed unscheduled. Settings and source-sync unchanged. FAILED count did not increase.

Smoke task `ad24f373-700e-49d0-b5e0-31567e9e5bfd` via capture → Object PATCH interval → status transitions → clear → soft-delete. Capture left the interval NULL. Set 2026-09-12 20:00–20:45 Europe/Moscow; `due_at` stayed NULL. Same Object.id in `scheduled_work` only. open visible, done visible, cancelled hidden. Clear returned both planned fields to NULL and removed the task from `scheduled_work`. Normal soft-delete. Zero Scheduled Work calendar writes or OpenAI calls. Temporal Signals healthy. Cost Guards unchanged.

Production settings remain: `temporal_signals_enabled=true`, `openai_daily_token_limit=1500000`, assistant model `gpt-5.6-luna`, proactive=false / interval 60, `auto_label_enabled=true`, source sync intervals unchanged.
