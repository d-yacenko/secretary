# Current task — Availability A-R1

## Status

**Availability A-R1: implemented / awaiting Architect review**

Branch: `review/availability-a`
Exact A-R1 application SHA: `e535adfb9857d2407fac06998a1a5a14c2b73502`
Exact application parent: `acc11e997670b15efbc39faee8c5c60d328683e8`
Availability A base: `8d25c1ab6672744e85652ec917970d704553d5db`
Production application remains: `76721b16650c49ce32b6405e8a001bdc6822bec4`
Production Alembic: **0038 / 0038**
Migration: **NONE**. Alembic remains **0038 / 0038**. No `0039`. No backfill.
No deploy.

## Contract

Availability is a derived read model. It is calculated on demand from already materialized confirmed Google/Yandex calendar event Objects. It does not persist free slots, busy intervals, availability Objects/Edges/tables, or copy provider calendars.

Week layers remain: confirmed calendar events = HARD; `scheduled_work` = SOFT; `temporal_hints` = TENTATIVE. Only HARD confirmed calendar commitments block availability. `scheduled_work` and `temporal_hints` do not block.

Authoritative availability includes every matching HARD event in the bounded <=7-day window. There is no event-count cap. Unknown-end HARD events (`due_at=NULL`) are relevant when `start_at < window_end` with no lower bound at `window_start`. That case is fail-closed: `availability_complete=false`, id in `unknown_end_event_ids`, `free_intervals=[]`. Known-end busy intervals may still be returned. Week/Today `event_overlaps_window` start-in-window semantics are unchanged.

`GET /availability` is read-only and authenticated. No provider fetch, no provider writes, no OpenAI, no automatic scheduling, no calendar writes.

## Not in this phase

No deploy. No Flutter changes. No Cost Guard / settings / source-sync changes. Production settings remain: `temporal_signals_enabled=true`, `openai_daily_token_limit=1500000`, assistant model `gpt-5.6-luna`, proactive=false / interval 60, `auto_label_enabled=true`, source sync intervals unchanged. Encrypted Architect context untouched.
