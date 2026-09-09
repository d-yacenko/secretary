# Current task — Temporal Correctness B

## Status

Temporal Correctness B — Recurring Calendar Materialization & Today: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Inbox Workflow Controls. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/temporal-correctness-recurring-calendar-b`

- Exact production / parent: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Temporal A: **CLOSED / DEPLOYED**; Inbox infinite scroll production-confirmed
- Temporal B application: see HEAD after commit

## Production truth

- Production application SHA: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Design Quality Pass A/B / B-R1: **CLOSED / PRODUCTION**
- Temporal Correctness A: **CLOSED / DEPLOYED**; Inbox infinite scroll works without the previous finite limit
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF** (`proactive_enabled=false`, interval 60)
- Real-user `auto_label_enabled`: **true**
- Temporal Correctness B: **current**
- Next after Temporal B (record only): **Inbox Workflow Controls — Review Marker & Manual Bookmarks**
- After Workflow Controls (record only): **Design Quality Pass C**
- Graph Advanced UX: **later / not started**
- Encrypted Architect context: untouched (`origin/main` authoritative)

## Scope

Calendar connectors materialize recurring occurrences as `Object(kind="event")`. `TodayService` only queries materialized Event Objects. No RRULE in TodayService. No second recurrence table/engine. No source writes. Temporal A Inbox contract frozen. Flutter unchanged.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
