# Current task — Design Quality Pass C — Labels, Object Presentation & Graph Bookmark Presentation

## Status

Design Quality Pass C is implemented on `review/design-quality-pass-c` and **awaiting Architect code + visual review**.

Do **not** deploy. Do **not** start Graph Advanced UX.

## Production / lineage

- Canonical production/base/parent: `9f0abe0d44cb91dbf0a555f2ae79aa5e2b21d25b`
- Temporal Correctness C / C-R1: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Inbox Workflow Controls A / A-R3: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Temporal A: **CLOSED / DEPLOYED**
- Temporal B: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Alembic: **`0034 / 0034`** (no migration in this phase)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Bookmark Presentation: **IN SCOPE for Pass C only**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## Scope

Client-side visual/presentation quality pass only:

- quieter compact Labels (`ObjectLabelStrip`) with no taxonomy parsing;
- shared Inbox/Today/Search object presentation primitives;
- Review Marker and bookmark physical visual language;
- Graph node bookmark overlay via the shared session controller;
- date separator and desktop LCD clock polish.

No backend/schema/API/migration/recurrence changes.

## Technical debt (record only, not fixed here)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
