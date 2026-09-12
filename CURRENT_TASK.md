# Current task — OpenAI Cost Guard C-R1 — in-flight usage + transcription accounting + timezone reset

## Status

**OpenAI Cost Guard C-R1: corrected / awaiting Architect review**

Branch: `hotfix/openai-cost-guard-c`
Exact parent: `27e0c097c43a81bbb9925f13a83734cc722a3201`
Production application SHA remains: `04f20f21d5460c9901d811ebd53863a370f85eda`
Alembic: **0036** unchanged (`user_settings.openai_daily_token_limit`)

Do **not** deploy this phase.
Do **not** merge/rebase Temporal Signals A.
Do **not** begin Cost Guard D.
Do **not** add dollar pricing or anomaly detection.

## C-R1 corrections

- Sequential paid calls in the same unfinished AI trace include that trace's actual uncommitted `input_tokens + output_tokens` in the pre-call check. Assistant round `extra_tokens` is not double-counted (max vs in-flight).
- Transcription preserves real OpenAI SDK token usage (`UsageTokens`) across the threadpool and writes it to audit. Duration-only usage is not estimated into tokens.
- PATCH `/me/settings` timezone releases budget-parked jobs so the worker can run them or repark to the new timezone's `reset_at`.

## Out of this phase

Cost Guard D, Temporal Signals, dollar pricing, Flutter changes, model/sync changes.
