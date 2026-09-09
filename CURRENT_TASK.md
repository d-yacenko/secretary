# Current task — Temporal Correctness A-R1

## Status

Temporal Correctness A-R1 — preserve deep-scroll Inbox refresh + real Android 23 APK: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Temporal Correctness B. Do **not** start Design Quality Pass C / Graph Advanced UX.

## Branch

`review/temporal-correctness-inbox-feed-a`

- Production: `2c88cb5f18680c699eb11c970e34e3629271a66b`
- Temporal A application: `e79a977bbeb5d85fc35829b05e5cdae3fdc42e1e`

## Production truth

- Production application SHA: `2c88cb5f18680c699eb11c970e34e3629271a66b`
- Design Quality Pass A/B / B-R1: **CLOSED / PRODUCTION**
- Alembic: **`0033 / 0033`**; **no `0034`**
- Android `minSdk`: **23** (product contract; A-R1 restores a real API-23 artifact after Flutter `build apk` had silently rewritten the Gradle file to `flutter.minSdkVersion` / 24)
- Proactive: **OFF** (`proactive_enabled=false`, interval 60)
- Real-user `auto_label_enabled`: **true**
- `POST /labels/by-objects` deployed
- Temporal Correctness B (recurring calendar): **not started**
- Design Quality Pass C: **deferred until Temporal A+B**
- Graph Advanced UX: **deferred**

## Scope

Keep accepted Temporal A feed/keyset. Corrective only: preserve accumulated Inbox tail on all normal first-page refreshes; pin Android plugins so debug APK manifest minSdk is 23.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.
