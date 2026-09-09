# Current task — Inbox Workflow Controls A-R2

## Status

Inbox Workflow Controls A is implemented at `e779bc9a9834def7f2e6288e8dba85e83bbc33f3`.

A-R1 is at `d9d20c24ec0e2c4bbe21e1e024f0f2791ac443ee`.

A-R2 (loaded-tail marker visibility) is **awaiting Architect review** on `review/inbox-workflow-controls-a`.

Do **not** deploy. Do **not** start Design Quality Pass C. Do **not** start Graph Advanced UX.

Temporal Correctness B is **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**. Do not reopen recurrence/calendar logic.

## Production

- Exact SHA (live): `71e6573f349a7f6c045c762337252a56d1993d00`
- Temporal B Google recurring production: **PASS**
- Temporal B Yandex recurring fallback production: **PASS**
- Temporal A: **CLOSED**
- Alembic on production: **`0033 / 0033`** (this branch adds **`0034`**, not applied until deploy)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval **60**
- Real-user `auto_label_enabled`: **true**
- Design Quality Pass C / Graph: **not started**
- Encrypted Architect context: untouched

## Technical debt (record only, not fixed here)

Yandex Calendar attendee payload ordering/normalization can rewrite source Object metadata and `updated_at` with stable semantic event identity. Future: **Yandex attendee canonicalization / passive-sync metadata churn** (canonical dedupe/sort before metadata equality).

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
