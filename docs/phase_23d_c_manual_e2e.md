# PHASE 23D-C — deployment evidence & manual E2E readiness

Status: **ready for manual testing** (manual scenarios A–H **NOT YET RUN**).

## Integration

| Item | Value |
|------|-------|
| `origin/main` SHA | `b30b95e152656fbbec3e7a3028216ae05ad35659` |
| Branch | `main` fast-forward, no squash/rebase |

## VDS verification (`/opt/secretary`)

Captured 2026-08-30 from `root@185.233.107.66`.

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `b30b95e152656fbbec3e7a3028216ae05ad35659` |
| Branch | `main` |
| Tracked modifications | none (`git status --porcelain` empty) |
| Deployed | 2026-08-30 |

## Database migration

| Check | Result |
|-------|--------|
| Alembic current | `0018 (head)` |
| Alembic heads | `0018 (head)` |
| `pending_action_plans` migration | applied (`0018_pending_action_plans.py`, revision `0018`) |

## Backend health

| Check | Result |
|-------|--------|
| `curl -sS http://127.0.0.1:18080/health` | `{"status":"ok"}` |
| `infra-api-1` | Up |
| `infra-db-1` | Up (healthy) |
| `infra-worker-1` | Up |

API bind: `127.0.0.1:18080` (localhost on VDS host only).

## Production smoke checks (pass/fail only)

Ephemeral operator token issued and revoked; no bearer tokens, personal content, or transcripts recorded.

| Check | Pass |
|-------|------|
| Authentication (`GET /me`) | yes |
| Read-only Assistant (`POST /assistant/message`) | yes |
| Search API (`GET /search`) | yes |
| Object API (`GET /objects/{id}` responds) | yes |
| `/assistant/transcribe` reachable (`POST` without body → 422) | yes |

No mutating Assistant smoke data created.

## Client build proof (commit `b30b95e`, not re-run for this doc step)

Executed earlier against accepted `main` / `b30b95e`.

| Check | Result |
|-------|--------|
| `flutter analyze` | PASS (no issues) |
| `flutter test` | PASS (112 tests) |
| `flutter build apk --debug` | PASS |
| APK local path | `/home/d.yacenko/work/secretary/client/build/app/outputs/flutter-apk/app-debug.apk` |
| APK SHA-256 | `bc07649bf70cb03791ae20062802eb68b857261e99cb84446288c445f947763f` |
| `minSdk` in `client/android/app/build.gradle.kts` | `23` |

APK binary not committed. Configure server URL and bearer token in app setup (existing flow).

## Manual E2E

| Item | Status |
|------|--------|
| Scenarios A–H | **NOT YET RUN** |
| PHASE 23D-C completion | **not claimed** |

Await user manual validation. Record findings as scenario / expected / actual / severity.

## HTTPS connectivity (2026-08-30)

Path-based proxy on existing `web-itx.duckdns.org` nginx HTTPS server block.

| Item | Value |
|------|-------|
| Public Secretary base URL | `https://web-itx.duckdns.org/secretary` |
| Android app server URL | `https://web-itx.duckdns.org/secretary` (no `/health` suffix) |
| Internal backend | `http://127.0.0.1:18080` (still `127.0.0.1` only; not on `0.0.0.0`) |
| nginx config backup | `/etc/nginx/sites-enabled/web-itx-ssl.conf.bak-phase23dc-20260830123256` |
| TLS certificate | renewed via Certbot webroot (previous cert expired 2026-07-06) |

Route mapping (prefix stripped):

| Public | Backend |
|--------|---------|
| `/secretary/health` | `http://127.0.0.1:18080/health` |
| `/secretary/me` | `http://127.0.0.1:18080/me` |
| `/secretary/assistant/message` | `http://127.0.0.1:18080/assistant/message` |
| `/secretary/assistant/transcribe` | `http://127.0.0.1:18080/assistant/transcribe` |

| Check | Result |
|-------|--------|
| `nginx -t` | PASS |
| `systemctl reload nginx` | OK |
| Public `GET https://web-itx.duckdns.org/secretary/health` | PASS (`HTTP 200`, `{"status":"ok"}`) |
| Public authenticated `GET /secretary/me` | PASS (`HTTP 200`; ephemeral token, not recorded) |
| Existing root site `GET https://web-itx.duckdns.org/` | PASS (`HTTP 200`) |
| Other virtual hosts / services | not modified |

`client_max_body_size 12m` on `/secretary/` for 10 MiB transcription uploads.
