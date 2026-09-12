# Current task — Availability A

## Status

**Availability A: implemented / awaiting Architect review**

Branch: `review/availability-a`
Exact implementation SHA: branch tip of `review/availability-a` after this commit
Exact base/parent: `8d25c1ab6672744e85652ec917970d704553d5db`
Production application remains: `76721b16650c49ce32b6405e8a001bdc6822bec4`
Production Alembic: **0038 / 0038**
Migration: **NONE**. Alembic remains **0038 / 0038**. No `0039`. No backfill.
No deploy.

## Contract

Availability is a derived read model. It is calculated on demand from already materialized confirmed Google/Yandex calendar event Objects. It does not persist free slots, busy intervals, availability Objects/Edges/tables, or copy provider calendars.

Week layers remain: confirmed calendar events = HARD; `scheduled_work` = SOFT; `temporal_hints` = TENTATIVE. Only HARD confirmed calendar commitments block availability. `scheduled_work` and `temporal_hints` do not block. Non-calendar providers, rejected events, and deleted events do not block.

`GET /availability` is read-only and authenticated. No provider fetch, no provider writes, no OpenAI, no automatic scheduling, no calendar writes.

Unknown-end confirmed calendar events fail closed: `availability_complete=false`, id listed in `unknown_end_event_ids`, `free_intervals=[]`. Known-end busy intervals may still be returned. Week visual nominal duration is display-only and is not availability truth.

## Not in this phase

No deploy. No Cost Guard / settings / source-sync changes. Production settings remain: `temporal_signals_enabled=true`, `openai_daily_token_limit=1500000`, assistant model `gpt-5.6-luna`, proactive=false / interval 60, `auto_label_enabled=true`, source sync intervals unchanged. Encrypted Architect context untouched.
