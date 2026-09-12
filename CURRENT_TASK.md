# Current task — Temporal Signals A

## Status

**Temporal Signals A: CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**

Exact accepted/deployed application SHA: `6cf1c04fb87dc99b050b6d83d0995db5c2f9e876`
Branch: `review/temporal-signals-a-integration`
Production Alembic: **0037 / 0037**
Migration: **0037 → 0036** (`user_settings.temporal_signals_enabled`)

Real-user `temporal_signals_enabled=true`. No historical backfill. Cost Guards A+B+C remain intact / production accepted.

Current real-user `openai_daily_token_limit=1500000`. Assistant model `gpt-5.6-luna`. Proactive **false** / interval 60. `auto_label_enabled=true`. Source sync intervals unchanged.

## Production acceptance

New real Gmail processed through normal source sync. Exact-time signal for 14 Sep 2026 15:30 Europe/Moscow. Result: `hint_created`. `due_at=NULL`. `participation=expected`. Source evidence signature/version correctly bound. Week exposes the object only through `temporal_hints`, not events/busy. One paid Temporal extraction for that source revision; no duplicate extraction for unchanged `source_signature` during ~22 min observation. No Temporal hot loop. No new FAILED jobs. Source sync healthy. Cost Guard remained not exhausted. No manual enqueue / synthetic job / backfill.

## Out of this phase

Historical backfill, Telegram Temporal, Cost Guard D, dollar pricing, anomaly detection. Do not invent the next phase.
