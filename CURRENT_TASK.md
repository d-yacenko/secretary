# Current task — OpenAI Cost Guard C — per-user daily OpenAI token hard cap

## Status

**OpenAI Cost Guard C: CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**

Exact application SHA: `7b580d955085ae7a5b3ae8c0a80b7f580cb938b1`
Branch: `hotfix/openai-cost-guard-c`
Exact parent of deployed SHA: `27e0c097c43a81bbb9925f13a83734cc722a3201`
Previous production: `04f20f21d5460c9901d811ebd53863a370f85eda`
Production Alembic: **0036 / 0036** (`user_settings.openai_daily_token_limit`)

Final production fuse: **NULL / disabled**. Do **not** change the user's `openai_daily_token_limit`.
Do **not** begin Cost Guard D.
Do **not** merge/rebase Temporal Signals A.
Do **not** add dollar pricing or anomaly detection.

## Production fuse test (PASSED)

- U at arming: 293952 actual tokens today
- temporary limit: 293952
- 2 `/assistant/message` requests => HTTP 429 `code=openai_daily_budget_exhausted`
- zero new assistant `model_round` / `model_round_failed` paid events
- `tokens_used_today` did not increase while armed
- one warning notification for the local day; no duplicate on second request
- source sync stayed healthy
- no FAILED/job storm
- naturally blocked embed jobs parked until Moscow local-day reset
- parked attempts remained 0
- blocked embedding traces had zero `model_round`
- clearing the limit released parked jobs without manual retry
- final `openai_daily_token_limit=NULL`
- final `exhausted=false`
- application SHA and Alembic unchanged

## Deployed C-R1 corrections (included in the accepted SHA)

- Sequential paid calls in the same unfinished AI trace include that trace's actual uncommitted `input_tokens + output_tokens` in the pre-call check. Assistant round `extra_tokens` is not double-counted (max vs in-flight).
- Transcription preserves real OpenAI SDK token usage (`UsageTokens`) across the threadpool and writes it to audit. Duration-only usage is not estimated into tokens.
- PATCH `/me/settings` timezone releases budget-parked jobs so the worker can run them or repark to the new timezone's `reset_at`.

## Out of this phase

Cost Guard D, Temporal Signals, dollar pricing, Flutter changes, model/sync changes.
