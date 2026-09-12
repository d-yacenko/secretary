# Current task — Availability A

## Status

**Availability A: CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**

Branch: `review/availability-a`
Exact production application SHA: `e535adfb9857d2407fac06998a1a5a14c2b73502`
Production Alembic: **0038 / 0038**
Migration: **NONE**. No `0039`. No backfill.
Docs-only closure parent: `f757a566c1bdb9937c42e615cf99045bd10eb981`
No docs-only deploy.

## Contract

Availability is a deterministic derived read model calculated on demand from already materialized confirmed Google/Yandex calendar events.

Only HARD confirmed calendar commitments block availability.

Week time layers remain:

1. confirmed calendar events = HARD
2. `scheduled_work` = SOFT
3. `temporal_hints` = TENTATIVE

`scheduled_work` does **not** block availability. `temporal_hints` do **not** block availability.

Availability persists no free slots, persists no busy intervals, creates no Object/Edge/table, performs no provider fetch, performs no provider write, performs no OpenAI/model call, and creates no background jobs.

`GET /availability` is authenticated and read-only. Window is bounded to <= 7 days. There is no authoritative event-count cap.

Known-end HARD overlap: `start_at < window_end` AND `due_at > window_start`. Unknown-end HARD: `due_at IS NULL` AND `start_at < window_end`. Unknown-end is fail-closed: `availability_complete=false`, id in `unknown_end_event_ids`, `free_intervals=[]`. Week/Today unknown-end display semantics remain unchanged.

Known HARD intervals are clipped to the requested window. Overlapping and directly adjacent HARD intervals merge. Free intervals are the complement of merged HARD intervals and respect `min_duration_minutes`. Timezone arithmetic uses aware instants / UTC arithmetic.

## Production acceptance

Production `76721b16650c49ce32b6405e8a001bdc6822bec4` → `e535adfb9857d2407fac06998a1a5a14c2b73502`. Alembic remained **0038 / 0038**. `/health` healthy. api / worker / db healthy. FAILED `1435` → `1435`.

Production settings unchanged: `temporal_signals_enabled=true`, `openai_daily_token_limit=1500000`, assistant model `gpt-5.6-luna`, proactive=false / interval 60, `auto_label_enabled=true`, source sync intervals unchanged.

Main real-data smoke, timezone `Europe/Moscow`, window 2026-09-12 09:00–18:00 Europe/Moscow. HARD events: `53584b6f-817c-421d-8616-0a1f5d1a576a` google_calendar 09:50–11:20 MSK; `3a7e38ef-9942-41eb-88c0-0dc8dedd6974` yandex_calendar 13:30–14:00 MSK. Returned HARD busy matching those events and free complement 09:00–09:50, 11:20–13:30, 14:00–18:00, all >= requested 30 minutes. Independent DB-vs-API comparison matched.

Clip smoke: confirmed event starting before the requested window was correctly clipped. Natural overlap/merge smoke: 17 Sep 2026 18:00–20:00 MSK contained a Google all-day event plus a timed Google event; Availability returned one merged HARD busy interval covering the requested window with both event ids. Temporal hint `aafcdfde-ad0e-4b38-bcd4-e546a43afff8` did **not** block availability.

No natural production unknown-end case was available; accepted A-R1 automated regressions cover unknown-end inside/before the query window and exclusion at or after `window_end`. No natural `scheduled_work` overlap was available during smoke; accepted automated regression proves `scheduled_work` does not block. Empty-window smoke returned one full free interval. Deployed Availability code contains no 500-event cap; >500-event correctness is covered by accepted A-R1 regression.

Availability caused zero provider writes, zero provider FreeBusy calls, zero Availability jobs, zero Availability OpenAI calls, and zero Object/Edge mutations. Temporal Signals remained healthy. Scheduled Work / Week remained healthy. Source sync remained healthy.

Flutter production runtime showed no discovered runtime error. Wayland automation could not independently click/capture the Flutter GTK window (`xdotool` cannot see it; `flutter screenshot` is unsupported on Linux). Recorded as an automation/capture limitation, not a product defect.

Encrypted Architect context untouched.
