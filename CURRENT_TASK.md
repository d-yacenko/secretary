# Current task — Scheduled Work A

## Status

**Scheduled Work A: implemented / awaiting Architect review**

Branch: `review/scheduled-work-a`
Exact base/parent: `9dd26f271fa4bab94b3e60d6cbc840ff19b4f04d`
Exact implementation SHA: `PLACEHOLDER_IMPLEMENTATION_SHA`
Migration: **0038 → 0037** (`objects.planned_start_at`, `objects.planned_end_at`)
No deploy.

Production remains `6cf1c04fb87dc99b050b6d83d0995db5c2f9e876`.
Production Alembic remains **0037 / 0037**.

Temporal Signals A remains **CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**.

Do not change production settings:
- `temporal_signals_enabled=true`
- `openai_daily_token_limit=1500000`
- assistant model `gpt-5.6-luna`
- proactive=false / interval 60
- `auto_label_enabled=true`

## This phase

Explicit task planned execution interval (`planned_start_at` / `planned_end_at`) as Week layer 2.

Scheduled work is not a calendar event, not busy time, and does not write Google/Yandex calendars.

`due_at` remains a deadline. No backfill. No OpenAI/model/cost-guard changes.

## Out of this phase

Availability / free-busy, automatic placement, drag-and-drop, calendar writes, converting hints or deadlines into planned intervals, recurring tasks, historical backfill, Telegram Temporal.
