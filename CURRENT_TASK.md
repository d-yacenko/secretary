# Current task — Design Quality Pass C-R2 — Full-width bookmark overlay + stronger date separator

## Status

Pass C / C-R1 is **deployed**. Broad human visual QA **passed**.

C-R2 corrective is implemented on `review/design-quality-pass-c` and **awaiting Architect review**.

Do **not** redeploy until Architect accepts C-R2. Do **not** start Graph Advanced UX.

## Production / lineage

- Production before R2 / C-R1 SHA: `0ea5b8358418d1c3dec85fbc694c0489b6f1153f`
- Exact C-R2 parent: `0ea5b8358418d1c3dec85fbc694c0489b6f1153f`
- Pass C: `b0cf7c9d63dcf19b2b4933d6b81395e5ae06b3a1` (accepted)
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## Remaining human visual findings (C-R2)

- full-width bookmark overlay (active bookmark must not shrink the card)
- stronger date pill on Inbox separators

Accepted and frozen: Inbox density, compact labels, actions+labels row, timestamp alignment, Review Marker, bookmark grammar, LCD, Today alignment, Search, Object Detail, Graph bookmark presentation/propagation, Android/narrow usability, C-R1 hit target.

## C-R2 scope

Client-only presentation:

- `ObjectBookmarkRibbon` overlays the tab; no whole-card trailing reservation
- timestamp/title protected with **internal** header `trailingReserve`
- Inbox date separator keeps left/right lines; date/`Без даты` sit in the same compact pill

## Deferred (validated, NOT in R2)

- **Inbox Quick Actions — Swipe to Remove**: right-to-left swipe, red delete affordance, existing confirmation (`Удалить из Секретаря`), no immediate full-swipe delete. Conflicts with vertical scroll and Review Marker drag; implement later.

## Technical debt (record only)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
