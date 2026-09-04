# Current task — User Identity Profile / Self Resolution

## Status

Backend/runtime pass: **ARCHITECT REVIEW PENDING** at `b05e357e3939d54fd7f68b45d7c95a41e6797d7e`.

UI + final hardening pass: **implemented** at `45483a665cbdb9eebfe4622fefd6197809f4b9e8`.

UI hint corrective + VDS deploy: **complete** at `dc691abe69385dd99356dd2226b2a2364f0e3a1b`.

## Branch

`review/user-identity-profile`

## SHAs

Backend-pass application SHA: `b05e357e3939d54fd7f68b45d7c95a41e6797d7e`

UI + hardening application SHA: `45483a665cbdb9eebfe4622fefd6197809f4b9e8`

Current application SHA: `dc691abe69385dd99356dd2226b2a2364f0e3a1b`

Deployed VDS SHA: `dc691abe69385dd99356dd2226b2a2364f0e3a1b`

Docs HEAD (after this commit): pending push

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0028`

Android minSdk: `23`

## Delivered

### Backend (b05e357 + 45483a6)

- `UserIdentityProfile` table + Alembic `0028`
- Deterministic Russian `profile_text` parser
- `GET/PUT /me/identity`
- `UserIdentityContextService` — authored facts + connected accounts (Google, Yandex, Mattermost)
- Identity block in assistant instructions (not user message)
- `bound_runtime_identity_facts()` at final serialization boundary
- Unconditional first-person semantics even when no identity facts; no invented name when facts absent
- Removed `display_name` fallback from runtime facts

### Flutter (45483a6 + dc691ab)

- API: `GET/PUT /me/identity` (`UserIdentity`)
- Account section **«Моя идентичность»** with structured multiline editor and Russian explanation
- `identityProfileTemplateExample` as `TextField` hint (no separate «Пример структуры:» block)
- Load/save/error states; connected-account data not injected into editable field

## Verification (build host)

Backend `test_user_identity_profile.py`: **24 passed**

Flutter `test/account/profile_account_test.dart`: **14 passed** (hint, no example block, saved text)

Flutter analyze (changed files): **0 issues**

Ruff: not run (no backend changes in corrective pass)

## VDS deploy (2026-09-04)

```bash
cd /opt/secretary
git fetch origin review/user-identity-profile
git checkout review/user-identity-profile
git pull
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks:

- `git rev-parse HEAD` = `dc691abe69385dd99356dd2226b2a2364f0e3a1b` (clean checkout on branch)
- Alembic current/head: `0028`
- `/health`: `{"status":"ok"}` at `http://127.0.0.1:18080/health`
- Worker: healthy (`infra-worker-1` Up)
- Encrypted architect context blob SHA unchanged: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

## Production smoke

- `GET https://web-itx.duckdns.org/secretary/me/identity` → **200** (empty profile; Owner has no saved identity text)
- `PUT /me/identity` with `{"profile_text":""}` → **200** (no personal data written; profile remained empty)
- Desktop client «Not Found» on identity load was caused by missing `/me/identity` on pre-deploy VDS (`a0dfa5ce`); resolved after deploy to `dc691ab`

## Next

STOP — await architect review and manual semantic E2E with explicitly configured profile.

Do not start Format Parity.
