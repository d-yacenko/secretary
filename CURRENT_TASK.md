# Current task — Temporal Correctness B-R2

## Status

Temporal Correctness B-R2 — provider-authoritative continuation (Google nextPageToken; Yandex local vs provider truncation; bounded tombstone reads): **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Inbox Workflow Controls. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/temporal-correctness-recurring-calendar-b`

- Exact production: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Temporal B application: `df9ea214eb90e07a9f93f9a3728dce96e82bbfa1`
- B-R1: `99e03c898da4f698dd8398a10eb9925045f190e5`
- B-R2: awaiting Architect review (this commit)

## Production truth

- Production application SHA: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Temporal Correctness A: **CLOSED / DEPLOYED**
- Temporal Correctness B architecture: **accepted**; B-R1 accepted as parent; B-R2 focused corrective only
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF**
- Real-user `auto_label_enabled`: **true**
- Inbox Workflow Controls / Pass C / Graph: **not started**
- Encrypted Architect context: untouched

## Scope

Google live: provider `nextPageToken` is authoritative even for short or empty pages. Yandex: distinguish local vs provider truncation; local continuation from selected refs; provider 507 uses operational time-slice subdivision. Bounded tombstone DB prefix reads. No TodayService RRULE. No migration.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
