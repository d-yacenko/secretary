# Current task — Temporal Correctness B-R3-R2 (autoflush supersession)

## Status

Production remains frozen at `4d05801cc596dfe41244bd689da9524f5ce261a7`. Do **not** rollback. Do **not** deploy before Architect review.

Temporal Correctness B Google production acceptance: **PASS**.

Yandex functional production acceptance: **PASS** (PROVIDER_UNEXPANDED fallback; occurrence count=3 is EXPECTED via UNTIL).

B-R3-R2 (this branch): production `autoflush=False` legacy-master supersession must not be labeled `caldav_deleted`. Awaiting Architect review.

Do **not** start Inbox Workflow Controls. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Production

- Exact SHA (still live): `4d05801cc596dfe41244bd689da9524f5ce261a7`
- Previous production: `7d9adef7a79c0d926effaa9ca14dcb2bc0052965`
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF**, interval **60**
- Real-user `auto_label_enabled`: **true**
- Inbox Workflow Controls / Pass C / Graph: **not started**
- Encrypted Architect context: untouched

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
