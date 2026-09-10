# Current task — Design Quality Pass C-R4 — Touch Review Rail reset geometry + padding hygiene

## Status

C-R2 and C-R3 direction is **ACCEPTED**, not yet deployed.

C-R4 is implemented on `review/design-quality-pass-c` and **awaiting Architect review**.

Deploy the combined R2+R3+R4 candidate only after Architect accepts. Do **not** start Graph Advanced UX.

## Production / lineage

- Production SHA: `0ea5b8358418d1c3dec85fbc694c0489b6f1153f`
- C-R2 CODE ACCEPTED: `7b2fdb3af673e027bf6c2bc39799547982624474`
- C-R3: `c139ba23ff17f87216388ae87f8308c1d76ae56b`
- Exact C-R4 parent: `c139ba23ff17f87216388ae87f8308c1d76ae56b`
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## C-R4 scope

Client-only presentation/hit-target:

- reset rail hit target is only the left ~36 px, not the full ListView row
- non-source Inbox sections keep AppSpacing.lg left inset on touch
- source/date/marker rows keep the dedicated rail gutter

## Deferred (validated, NOT in R4)

- **Inbox Quick Actions — Swipe to Remove**

## Technical debt (record only)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
