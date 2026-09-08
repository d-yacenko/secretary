# Current task — Temporal Correctness A

## Status

Temporal Correctness A — Inbox Feed Semantics & Pagination: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Temporal Correctness B. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/temporal-correctness-inbox-feed-a`

Exact parent / current production: `2c88cb5f18680c699eb11c970e34e3629271a66b`

## Production truth

- Production application SHA: `2c88cb5f18680c699eb11c970e34e3629271a66b`
- Design Quality Pass A/B / B-R1: **CLOSED / PRODUCTION**
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF** (`proactive_enabled=false`, interval 60)
- Real-user `auto_label_enabled`: **true**
- `POST /labels/by-objects` deployed
- Temporal Correctness B (recurring calendar): **not started**
- Design Quality Pass C: **deferred until Temporal A+B**
- Graph Advanced UX: **deferred**

## Scope

Inbox chronological `feed_at` (same clock for order, cursor, and date separators), keyset pagination, Flutter infinite scroll. `primary_at` remains intrinsic/display date.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
