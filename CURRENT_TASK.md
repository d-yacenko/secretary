# Current task — User-Configurable Assistant Max Rounds

## Status

User Identity Profile / Self Resolution: **ARCHITECT ACCEPTED / CLOSED** at `dc691abe69385dd99356dd2226b2a2364f0e3a1b`.

Assistant Failure Taxonomy: **ARCHITECT ACCEPTED / DEPLOYED** at `89cdb996f5b4bea8d7830750a9b7b80a70db0aab`.

User-Configurable Assistant Max Rounds: **implemented and deployed** at `1401351e4fd146e376b3b702352bc10deac00e1b`.

## Branch

`review/user-identity-profile`

## SHAs

Application SHA: `1401351e4fd146e376b3b702352bc10deac00e1b`

Deployed VDS SHA: `1401351e4fd146e376b3b702352bc10deac00e1b`

Docs HEAD: pending after this commit

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0029`

Android minSdk: `23`

## Verification (build host, 2026-09-04)

Backend `test_assistant_max_rounds_settings.py` + failure taxonomy + phase_28a settings: **56 passed** (`test_action_plan_resume_uses_user_openai_key_when_deployment_empty` pre-existing local DB FK flake, unrelated)

Flutter profile account tests: **18 passed**

Flutter analyze: **0 errors** on changed files (pre-existing warnings elsewhere)

Ruff (changed backend files): **PASS**

Effective default/min/max: **6 / 1 / 12**

`MAX_ASSISTANT_TOOL_CALLS_PER_TURN`: **12** (unchanged)

## VDS deploy (2026-09-04)

```bash
cd /opt/secretary
git fetch origin review/user-identity-profile
git checkout review/user-identity-profile
git reset --hard 1401351e4fd146e376b3b702352bc10deac00e1b
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks:

- `git rev-parse HEAD` = `1401351e4fd146e376b3b702352bc10deac00e1b` (clean checkout on branch)
- Alembic current/head: `0029`
- `/health`: `{"status":"ok"}` at `http://127.0.0.1:18080/health`
- Worker: healthy (`infra-worker-1` Up)
- Encrypted architect context blob SHA unchanged: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

## Production smoke

- `GET /me/settings` → **200** (`assistant_max_rounds=6`, override `null`, bounds/default present)
- `POST /assistant/message` (simple one-word prompt) → **200** (user setting not changed)

## Next

STOP — do not start Format Parity.
