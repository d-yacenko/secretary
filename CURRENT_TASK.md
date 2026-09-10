# Current task — Temporal Correctness C — Recurring-Series Inbox Projection

## Status

Temporal Correctness C is implemented on `review/temporal-correctness-recurring-inbox-c` and **awaiting Architect review**.

Do **not** deploy. Do **not** start Design Quality Pass C. Do **not** start Graph Advanced UX / Graph bookmark visualization.

Inbox Workflow Controls A-R3 / A-R3-R1 remain **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**. Temporal A/B remain **CLOSED / DEPLOYED**.

## Production / lineage

- Canonical production/base/parent: `8db3c58b2ec1998f428750abc460e4fce292d7c0`
- Inbox Workflow Controls A-R3 / A-R3-R1: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Temporal A: **CLOSED / DEPLOYED**
- Temporal B: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Alembic: **`0034 / 0034`** (no migration in this phase)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Design Quality Pass C: **NOT STARTED**
- Graph Bookmark Presentation: **deferred to Design Quality Pass C**
- Encrypted Architect context: untouched

## Scope

Inbox-only projection: within a canonical provider recurring series, expose one Inbox representative for occurrences that were future at their own materialization time (`start_at > created_at`). Recurrence storage identity is unchanged. Today, Search, Object Detail, Graph, bookmarks, and occurrence Objects stay intact.

Do not group by title. Do not use `now()` for representative choice. Do not change Temporal A `feed_at` semantics or cursor format.

## Technical debt (record only, not fixed here)

Yandex attendee canonicalization / passive-sync metadata churn.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
