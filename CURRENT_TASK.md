# Current task — Design Quality Pass C-R3 — Touch Review Rail

## Status

C-R2 is **CODE ACCEPTED**, not yet deployed.

C-R3 Touch Review Rail is implemented on `review/design-quality-pass-c` and **awaiting Architect review**.

Deploy the combined R2+R3 candidate only after Architect accepts C-R3. Do **not** deploy C-R2 separately. Do **not** start Graph Advanced UX.

## Production / lineage

- Production SHA: `0ea5b8358418d1c3dec85fbc694c0489b6f1153f`
- C-R2 CODE ACCEPTED: `7b2fdb3af673e027bf6c2bc39799547982624474`
- Exact C-R3 parent: `7b2fdb3af673e027bf6c2bc39799547982624474`
- Pass C / C-R1 deployed: `0ea5b8358418d1c3dec85fbc694c0489b6f1153f`
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## C-R3 scope

Client-only interaction:

- Linux / desktop: keep existing Review Marker drag (card-wide drop = AFTER object, gap fallback, hover preview)
- Android / iOS: Touch Review Rail to the left of Inbox source cards; completed tap moves the marker; vertical swipe still scrolls
- LongPressDraggable is no longer required on touch
- Review Marker API / tuple / interpolation semantics frozen

## Deferred (validated, NOT in R3)

- **Inbox Quick Actions — Swipe to Remove**: right-to-left swipe, red delete affordance, existing confirmation (`Удалить из Секретаря`), no immediate full-swipe delete. Gesture separation preserved: vertical = scroll, future horizontal card swipe = delete, rail tap = move marker.

## Technical debt (record only)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
