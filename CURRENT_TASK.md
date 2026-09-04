# Current task — User Identity Profile / Self Resolution

## Status

Backend/runtime pass: **ARCHITECT REVIEW PENDING** at `b05e357e3939d54fd7f68b45d7c95a41e6797d7e`.

UI + final hardening pass: **implemented**, **deploy pending** (VDS unreachable from build host).

## Branch

`review/user-identity-profile`

## SHAs

Backend-pass application SHA: `b05e357e3939d54fd7f68b45d7c95a41e6797d7e`

Final application SHA: `45483a665cbdb9eebfe4622fefd6197809f4b9e8`

Deployed VDS SHA: **pending** — VDS host not reachable from build environment (`ya-site.duckdns.org` DNS failure; `adcm-bundle` has no `/opt/secretary`).

Docs HEAD (after this commit): pending push

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0028`

Android minSdk: `23`

## Delivered

### Backend hardening (45483a6)

- `bound_runtime_identity_facts()` at final serialization boundary (scalars, list items/counts, connected identifiers, merged emails, JSON cap)
- Unconditional first-person semantics in assistant instructions even when no identity facts; no invented name when facts absent
- Removed `display_name` fallback from runtime facts

### Flutter

- API: `GET/PUT /me/identity` (`UserIdentity`)
- Account section **«Моя идентичность»** with structured multiline editor, Russian explanation, visible template example
- Load/save/error states; connected-account data not injected into editable field

## Verification (build host)

Backend `test_user_identity_profile.py`: **24 passed**

Backend `test_assistant.py`: **51 passed**, 1 pre-existing failure (`test_assistant_nornickel_kursy_nl_provider`)

Flutter `test/account/profile_account_test.dart`: **13 passed**

Flutter analyze (changed files): 8 info/warning, 0 errors

Ruff (changed backend files): **PASS**

## Deploy (manual on VDS)

```bash
cd /opt/secretary
git fetch origin review/user-identity-profile
git checkout review/user-identity-profile
git pull
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks:

- `git rev-parse HEAD` = `45483a665cbdb9eebfe4622fefd6197809f4b9e8`
- Alembic `0028`
- `curl -sS http://127.0.0.1:18080/health`
- worker healthy
- production smoke: `GET /me/identity`, assistant message (no profile overwrite)

## Next

STOP — await architect review and manual semantic E2E with explicitly configured profile.

Do not start Format Parity.
