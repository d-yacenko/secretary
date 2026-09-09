# Current task — Temporal Correctness B-R1

## Status

Temporal Correctness B-R1 — stable live continuation & truthful hard bounds: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Inbox Workflow Controls. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/temporal-correctness-recurring-calendar-b`

- Exact production: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Temporal B application: `df9ea214eb90e07a9f93f9a3728dce96e82bbfa1`
- B-R1 parent: `df9ea214eb90e07a9f93f9a3728dce96e82bbfa1`

## Production truth

- Production application SHA: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Temporal Correctness A: **CLOSED / DEPLOYED**
- Temporal Correctness B architecture: **accepted**; B-R1 corrective only
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF**
- Real-user `auto_label_enabled`: **true**
- Inbox Workflow Controls / Pass C / Graph: **not started**
- Encrypted Architect context: untouched

## Scope

Correct Google frozen live page-chain, Yandex local truncation + operational href continuation, and Yandex occurrence mutation budget / incremental token replay. No TodayService RRULE. No migration.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
