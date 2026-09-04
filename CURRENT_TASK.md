# Current task — User Identity Profile + Assistant Failure Taxonomy

## Status

User Identity Profile / Self Resolution: **ARCHITECT ACCEPTED / CLOSED** at `dc691abe69385dd99356dd2226b2a2364f0e3a1b`.

Manual semantic E2E: **PASS** — first-person self-resolution matched the current user inside retrieved table content.

Assistant Failure Taxonomy: **ARCHITECT ACCEPTED / DEPLOYED** at `89cdb996f5b4bea8d7830750a9b7b80a70db0aab`.

## Branch

`review/user-identity-profile`

## SHAs

User Identity application SHA (closed): `dc691abe69385dd99356dd2226b2a2364f0e3a1b`

Assistant Failure Taxonomy application SHA: `89cdb996f5b4bea8d7830750a9b7b80a70db0aab`

Deployed VDS SHA: `89cdb996f5b4bea8d7830750a9b7b80a70db0aab`

Docs HEAD: `9624b1b3cbfd8195a331ef6b7505d0e8dcf89ff5`

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0028`

Android minSdk: `23`

## Verification (build host, 2026-09-04)

Backend `test_assistant_failure_taxonomy.py`: **16 passed**

Backend Assistant/API touched tests: **16 passed** (focused set; `test_action_plan_resume_uses_user_openai_key_when_deployment_empty` pre-existing local DB FK flake, unrelated)

Flutter API error tests: **4 passed**

Flutter Assistant structured error test: **1 passed**

Flutter analyze (changed files): **0 errors** (1 info: `use_super_parameters`)

Ruff (changed backend files): **PASS**

`MAX_ASSISTANT_ROUNDS`: **6** (unchanged)

## VDS deploy (2026-09-04)

```bash
cd /opt/secretary
git fetch origin review/user-identity-profile
git checkout review/user-identity-profile
git reset --hard 89cdb996f5b4bea8d7830750a9b7b80a70db0aab
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks:

- `git rev-parse HEAD` = `89cdb996f5b4bea8d7830750a9b7b80a70db0aab` (clean checkout on branch)
- Alembic current/head: `0028`
- `/health`: `{"status":"ok"}` at `http://127.0.0.1:18080/health`
- Worker: healthy (`infra-worker-1` Up)
- Encrypted architect context blob SHA unchanged: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

## Production smoke

- `GET /me/identity` → **200** (existing profile intact; read-only)
- `POST /assistant/message` (simple one-word prompt) → **200**

## Next

STOP — do not start Format Parity.
