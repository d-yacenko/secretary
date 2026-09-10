# Current task — Inbox Quick Actions — Swipe to Remove A-R1

## Status

A-R1 corrective implemented on `review/inbox-quick-actions-swipe-remove-a`. **Awaiting Architect review.** Do **not** deploy A-R1 until Architect accepts.

Design Quality Pass C: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**. Do not reopen or redesign Pass C.

## Production / lineage

- Production remains: `4d9391e65d7c3251fe854903b83f60fe4d395779`
- A: `16e1ac0d48327e97eca259735ad270e95772d415` — **CODE ACCEPTED / not production accepted**
- A-R1: current corrective on `review/inbox-quick-actions-swipe-remove-a` (exact parent of A-R1 = A)
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Unified Week + Availability: later
- Encrypted Architect context: untouched

## Product rule

EXTERNAL / explicitly provider-backed source object + deliberate armed full swipe = confirmation itself.

Secretary-native / unknown = modal confirmation remains.

No Undo. Review Marker unchanged.

## Semantics

- touch only (Android / iOS); Linux desktop unchanged
- endToStart (right-to-left) only
- eligible provider-backed objects: deliberate armed full swipe deletes immediately (no dialog)
- task / note / unknown: swipe still opens the existing confirmation dialog
- Object Detail still uses `confirmAndDeleteObject` (modal unchanged)
- Remove from Secretary only; provider source untouched
- local row removal after successful DELETE
- bookmark cache forget; no bookmark API mutation on Object delete
- Review Marker preserved even when its anchor Object is removed
- no DELETE/PUT `/inbox/review-marker` as a side effect of Object deletion

## Out of scope

- sticky 1/3-open action buttons / custom spring physics
- mouse-drag swipe on Linux
- notifications / Today / Search / Graph swipe
- undo / provider DELETE
- backend, Review Marker API, schema, Graph Advanced UX, Unified Week, Availability, Telegram, provider brand assets

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
