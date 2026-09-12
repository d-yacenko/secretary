# Current task — Scheduled Work A-R1

## Status

**Scheduled Work A-R1: implemented / awaiting Architect review**

Branch: `review/scheduled-work-a`
Exact A-R1 application SHA: `76721b16650c49ce32b6405e8a001bdc6822bec4`
A-R1 parent: `6a3994f454ebf6ab805581da995ee4c629bbacde`
Scheduled Work A code SHA: `bae22631b2455aa6583721089231133e65ba8481`
Migration: **0038 → 0037** (`objects.planned_start_at`, `objects.planned_end_at`)
No deploy.

Production remains `6cf1c04fb87dc99b050b6d83d0995db5c2f9e876`.
Production Alembic remains **0037 / 0037**.

## This corrective

Week `scheduled_work` is fail-closed: only `open` / `in_progress` / `done`.
NULL, legacy `completed`, cancelled/archived/deleted, and unknown statuses are excluded.

## Out of this phase

Availability / free-busy, automatic placement, drag-and-drop, calendar writes, converting hints or deadlines into planned intervals, recurring tasks, historical backfill, Telegram Temporal.
