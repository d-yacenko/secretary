# Current task — Inbox Quick Actions — Swipe to Remove A

## Status

Implemented on `review/inbox-quick-actions-swipe-remove-a`. **Awaiting Architect review.** Do **not** deploy until Architect accepts.

Design Quality Pass C: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**. Do not reopen or redesign Pass C.

## Production / lineage

- Production base / exact parent: `4d9391e65d7c3251fe854903b83f60fe4d395779`
- Branch: `review/inbox-quick-actions-swipe-remove-a`
- Alembic: **`0034 / 0034`** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Advanced UX: **NOT STARTED / later**
- Unified Week + Availability: later
- Encrypted Architect context: untouched

## Semantics

- touch only (Android / iOS); Linux desktop unchanged
- endToStart (right-to-left) only
- confirmation required via existing `confirmAndDeleteObject`
- Remove from Secretary only; provider source untouched
- local row removal after successful DELETE
- bookmark cache forget; no bookmark API mutation on Object delete
- Review Marker preserved even when its anchor Object is removed
- no DELETE/PUT `/inbox/review-marker` as a side effect of Object deletion

## Out of scope

- mouse-drag swipe on Linux
- notifications / Today / Search / Graph swipe
- backend, Review Marker API, schema, Graph Advanced UX, Unified Week, Availability, Telegram, provider brand assets

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
