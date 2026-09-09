# Current task — Temporal Correctness B-R3 (Yandex recurrence fallback)

## Status

Production remains frozen at `7d9adef7a79c0d926effaa9ca14dcb2bc0052965`. Do **not** rollback. Do **not** deploy before Architect review.

Temporal Correctness B Google production acceptance: **PASS**.

Yandex remaining production defect diagnosis: **PROVIDER_UNEXPANDED** (resource-specific; calendar-query/multiget/`c:expand` succeed, but this weekly resource returns an RRULE master with zero RECURRENCE-ID occurrences).

B-R3 (this branch): bounded **python-dateutil** Yandex connector fallback for that shape. Awaiting Architect review.

Do **not** start Inbox Workflow Controls. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Production

- Exact SHA (still live): `7d9adef7a79c0d926effaa9ca14dcb2bc0052965`
- Previous production: `10e9d2d290da37489ee7dbfa0902b587d3ca3768`
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF**, interval **60**
- Real-user `auto_label_enabled`: **true**
- Inbox Workflow Controls / Pass C / Graph: **not started**
- Encrypted Architect context: untouched

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
