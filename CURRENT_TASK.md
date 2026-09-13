# Current task — Teams A + Communication Action Plan Integrity

## Status

**Teams A: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** on `review/teams-a`.

Not CLOSED. Not PRODUCTION ACCEPTED.

CODE ACCEPTED application SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`  
Exact deployed production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`  
Previous production SHA: `c5d288444cc5053e79c0942cdbc23af3eebbbb50`  
Alembic: **0040 / 0040**  
Migration: `0040_teams_accounts.py`. No `0041`.

This ledger transition is docs-only. Do not change application code. Do not deploy. Do not touch production configuration.

## Canonical base

SHA: `fd5d1497215e4c72033274908b69aebe42e175a9`  
Branch: `review/telegram-a`  
Commit: `Close Telegram A after production activation`

Telegram A remains CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED. Do not reopen or redesign Telegram A.

## Production application (unchanged this record)

Exact application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e` remains detached on VDS `/opt/secretary`. Alembic remains **0040 / 0040**. Docs-only commits are not deployed.

## Microsoft runtime configuration

Microsoft production credentials are present. Runtime:

- `teams_is_configured()` == true
- `GET /connections` Teams `configured=true`
- `connected=false`
- `reconnect_required=false`

Redirect remains `https://web-itx.duckdns.org/secretary/auth/teams/callback`. Secret values are not recorded here.

## Microsoft OAuth / live E2E

The user initiated real Microsoft OAuth with a work/school account. Microsoft successfully recognized the Secretary Entra application and that account.

OAuth was then blocked by the organization's Microsoft Entra tenant policy with **Need admin approval**.

This is an **EXTERNAL TENANT ADMIN-CONSENT BLOCKER**, not a Secretary code defect.

Required configured Graph delegated permissions:

- `User.Read`
- `Chat.Read`
- `ChatMessage.Send`
- plus OIDC `openid` / `profile` / `offline_access`

The accidental `ChatMessage.Read` permission was removed from Entra.

No Teams account or token was created. No Teams send occurred. Recurring Teams sync, inbound Teams object, first-turn Pending Action Plan, and no-write-before-approval were not reached. Real Secretary-originated Teams send: **not executed, not claimed as production-tested**.

## Subsequent phases

This external Entra admin-consent blocker **no longer blocks subsequent Secretary development phases**.

Teams production activation may be resumed later from the accepted/deployed SHA `eb3af922f804e6faf1d895fd14c0973981ce515e` after tenant admin consent becomes available.

Do not mark CLOSED / PRODUCTION ACCEPTED from this record.

## Stop

Docs-only ledger updated. No code change. No deploy. No production configuration change. Encrypted Architect context untouched.
