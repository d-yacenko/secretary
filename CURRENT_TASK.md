# Current task — Teams A + Communication Action Plan Integrity

## Status

**Teams A: CODE ACCEPTED / DEPLOYED / TEAMS ACTIVATION BLOCKED** on `review/teams-a`.

Not CLOSED. Not PRODUCTION ACCEPTED.

CODE ACCEPTED application SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`  
Exact deployed production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`  
Docs tip (not deployed): `511a3f36a20fc9bc91170d010d33cee486fd2c0b`  
Previous production SHA: `c5d288444cc5053e79c0942cdbc23af3eebbbb50`  
Alembic before: **0039 / 0039**  
Alembic after: **0040 / 0040**  
Migration: `0040_teams_accounts.py`. No `0041`.

Authorized work in this phase only:

1. Communication Action Plan Integrity corrective for the observed post-Telegram-A missing approval-card defect.
2. Microsoft Teams personal-chat (work/school, delegated OAuth) on the existing unified communications architecture.
3. Architect R1–R3 corrections (already CODE ACCEPTED in the deployed application SHA).
4. Exact-version production deploy of that SHA, Alembic `0039 → 0040`, then live Microsoft OAuth / inbound / Action Plan only if production Microsoft credentials already exist.

## Canonical base

SHA: `fd5d1497215e4c72033274908b69aebe42e175a9`  
Branch: `review/telegram-a`  
Commit: `Close Telegram A after production activation`

Telegram A remains CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED. Do not reopen or redesign Telegram A.

## Production evidence (2026-09-13)

Deployed from exact application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e` (detached on VDS `/opt/secretary`). Procedure: `git fetch`; `git checkout --detach eb3af922f804e6faf1d895fd14c0973981ce515e`; `cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`. Runtime HEAD after start is that SHA. Docs-tip `511a3f36…` was not deployed.

- `/health` 200 `{"status":"ok"}` internal and public
- api Up, worker Up, db healthy
- FAILED `1435` → `1435` (pre-existing; not repaired)
- Recurring sources continue: `sync_google_calendar`, `sync_google_gmail`, `sync_mattermost`, `sync_yandex_calendar`, `sync_yandex_mail` all `pending`, `last_error` empty, `last_success` after deploy (~2026-09-13T18:11Z)
- Settings unchanged: `assistant_model` NULL, `openai_daily_token_limit=1500000`, `temporal_signals_enabled=true`, `proactive_enabled=false`, `proactive_interval_minutes=60`, `auto_label_enabled=true`
- Source prefs unchanged (all interval 60s): gmail history 60, google_calendar, mattermost, yandex_calendar, yandex_mail history 30
- `teams_accounts` and `teams_oauth_states` exist; row counts 0 / 0 (no backfill)
- Existing accounts/objects unchanged: `mattermost_accounts=1`, `telegram_accounts=1`; no Teams objects; existing Gmail/Google/Yandex/Mattermost/Telegram counts unchanged
- `sync_teams` jobs: 0
- Runtime `teams_is_configured()`: false
- No job/OpenAI storm attributable to Teams. Recent embeds remain pre-existing `yandex_calendar` signature churn (Cost Guard B NONBLOCKING connector debt)
- No unintended external writes. Google/Yandex/Mattermost/Telegram credentials not changed. Production `.env` not rewritten.

## Microsoft OAuth / live E2E

**TEAMS ACTIVATION BLOCKED.** External setup blocker:

Production `.env` does not contain `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET`, or `MICROSOFT_REDIRECT_URI`. `SECRETARY_CREDENTIAL_KEY` is present. Running api/worker have empty Microsoft vars. Credentials were not invented and were not copied from elsewhere.

Expected production redirect after operator setup: `https://web-itx.duckdns.org/secretary/auth/teams/callback`  
Required delegated permissions: `openid profile offline_access User.Read Chat.Read ChatMessage.Send`  
Work/school (`organizations`) only. Consumer Microsoft accounts must not be enabled.

Until those values exist in production configuration and the Entra app is registered:

- Live Microsoft OAuth: not executed
- Recurring Teams sync: not executed
- Inbound Teams object: not executed
- First-turn explicit-send → Pending Action Plan: not executed
- No-write-before-approval reject: not executed
- Real Secretary-originated Teams send: **not executed, not claimed as production-tested** (activation blocked; this is not user-deferred write after a passing OAuth)

## Stop

Exact application SHA is deployed. Alembic is **0040 / 0040**. Production health PASS. Teams activation E2E cannot proceed without Microsoft app credentials.

Docs-only record of this deploy is not deployed.

Do not start Graph Refinement or any next phase. Do not invent Microsoft credentials. Do not mark CLOSED / PRODUCTION ACCEPTED until Architect authorizes a later activation pass after the external setup exists.
