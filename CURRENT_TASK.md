# Current task — Design Quality Pass B-R1

## Status

Design Quality Pass B-R1 — stale selected label cleanup: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/design-quality-b-label-visibility`

- Pass B application: `bff6cfb2174f2d3fb39bac6db1bf71cee72e4c4a`
- Exact parent for B-R1: `bff6cfb2174f2d3fb39bac6db1bf71cee72e4c4a`
- Pass A/A-R1 client baseline: `a5e31ab2a91e99c657f73f4dac525f961f3c9f69`

## Production truth

- Server production SHA: `d694c24150b5c6f62cca0d64db423fc34a88525c`
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23**
- Proactive: **OFF**
- Real-user `auto_label_enabled`: **true** (pre-existing)
- Source/label icon Asset Polish: **deferred**
- Graph Advanced UX: **deferred**

## Scope

Pass B remains: assigned labels on Inbox/Today/Search via `POST /labels/by-objects`.

B-R1: after Search catalog refresh, drop a selected label ID that is gone from the catalog, show true `Все`, and rerun an active search once without `label_id`. Rename keeps selection by ID.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
