# Current task — Design Quality Pass C-R5 — Touch card spacing + warm date pill + Today event separators

## Status

C-R2/R3/R4 are **deployed** and human-smoked. All previously requested Pass C functionality **passed**.

C-R5 is implemented on `review/design-quality-pass-c` and **awaiting Architect review**.

Do **not** deploy C-R5 until Architect accepts. Do **not** start Graph Advanced UX. Do **not** implement Inbox Quick Actions — Swipe to Remove.

## Production / lineage

- Production SHA / exact C-R5 parent: `03bbc621265a390aed10aa14094ff65f63c9d7ba`
- C-R2: `7b2fdb3af673e027bf6c2bc39799547982624474`
- C-R3: `c139ba23ff17f87216388ae87f8308c1d76ae56b`
- C-R4: `03bbc621265a390aed10aa14094ff65f63c9d7ba`
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## Remaining human visual findings (C-R5)

1. touch Inbox inter-card spacing
2. warm/distinct date pill
3. Today calendar event separators

Prior Pass C human smoke points passed and frozen: bookmark full-width overlay; bookmark palette/hit target; Review Rail on phone/tablet; vertical rail scroll; multi-screen marker placement; desktop Review Marker drag; labels; timestamps; Graph bookmark presentation; Search / Detail; general Inbox density.

## C-R5 scope

Client-only presentation:

- Android/iOS source cards get a compact ~4 px vertical gap; rail stays continuous through that strip
- date pill uses `tertiaryContainer` / `onTertiaryContainer` for all labels including `Без даты`
- Today calendar rows get a 1 px `outlineVariant` divider between events only

## Deferred (validated, NOT in R5)

- **Inbox Quick Actions — Swipe to Remove**

## Technical debt (record only)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
