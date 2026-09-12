# Current task — Temporal Signals A — integration onto Cost Guard C lineage

## Status

**Temporal Signals A integration: implemented / awaiting Architect review**

Exact integration SHA: `4bf706ac5ce57efd68fae803345af7cfddeece58`
Branch: `review/temporal-signals-a-integration`
Exact parent SHA: `bd6ebebc4d6475e45b8b7a91f3da253890d75ae2`
Accepted Temporal source head: `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
Temporal source base: `99658a6f893483317dcecaf15d886cd1ed8d692b`
Current production application (unchanged by this branch): `7b580d955085ae7a5b3ae8c0a80b7f580cb938b1`
Current production Alembic: **0036 / 0036**

Functional Temporal Signals A diff transferred from `99658a6` → `a9dc8c9` onto the Cost Guard C lineage. Old unpublished Temporal migration `0035` was not carried over.

Alembic on this branch: **0037 → 0036** (`user_settings.temporal_signals_enabled`)

Final lineage:

- 0035 — Cost Guard B / `objects.embedding_signature`
- 0036 — Cost Guard C / `openai_daily_token_limit`
- 0037 — Temporal Signals / `temporal_signals_enabled`

`temporal_signals_enabled`: Boolean, `nullable=False`, `server_default=false`. Default FALSE. No automatic enable. No historical backfill.

Paid Temporal OpenAI calls use the shared Cost Guard C daily token hard cap. Workload remains `background_temporal_signal`. Temporal reasoning/verbosity remain LOW. No separate Temporal budget.

NO DEPLOY. No production DB changes. Temporal remains disabled. Cost Guards A+B+C remain intact.

## Out of this phase

Deploy, enabling `temporal_signals_enabled`, historical backfill, Telegram Temporal, Cost Guard D, dollar pricing, anomaly detection, next phase.
