# Current task — Voice Assistant A

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not change Voice architecture.

## Inherited accepted phases

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED**

Application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

**Teams A remains: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e` (included in the Voice A production tree). Alembic **0040 / 0040**.

## Production deploy (Executor)

Detached on VDS `/opt/secretary`: `git checkout --detach 5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357` then `cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build api worker`. PostgreSQL volume `db_data` was not recreated. Only `api` and `worker` were rebuilt.

Pre-deploy backup: `/opt/secretary/backups/pre-voice-a-20260914T075123Z-eb3af922.dump` (custom format). Rollback: checkout `eb3af922` and rebuild `api`/`worker`; restore dump only if schema diverges.

Alembic **0040 / 0040** before and after. No Voice A/R2 migration. No `0041`.

Documented TTS/STT defaults were absent from production `.env` and were appended (not secrets): `OPENAI_TTS_MODEL=gpt-4o-mini-tts`, `OPENAI_TTS_VOICE=alloy`, `OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe`. Runtime resolved those values. Existing per-user OpenAI credential path remains (1 nonempty `user_openai_credentials` row).

FAILED jobs `1435` → `1435`. Internal `/health` 200. Public `https://web-itx.duckdns.org/secretary/health` 200.

Authenticated `POST /assistant/speech` with short harmless text: HTTP 200, `Content-Type: audio/mpeg`, 16896 audio bytes (MPEG ADTS). Objects `3472` → `3472`. Representations `452` → `452`. Smoke token revoked. No secrets printed. No external communication write.

## Clients for user manual test (same application SHA)

Android debug APK (existing test workflow):

`/tmp/secretary-voice-a-accepted/client/build/app/outputs/flutter-apk/app-debug.apk`

Install: `adb install -r /tmp/secretary-voice-a-accepted/client/build/app/outputs/flutter-apk/app-debug.apk`

`aapt dump badging` → `sdkVersion:'23'`. Source keeps `android.defaultConfig.minSdk = 23`.

Linux debug bundle (openSUSE Tumbleweed builder `voice-a-linux-builder:gst`, GStreamer devel 1.28.7, `libsecret-devel`, clang 19):

`/tmp/secretary-voice-a-accepted/client/build/linux/x64/debug/bundle/personal_secretary`

Run from the bundle directory (host GStreamer runtime required; this host has 1.26.7):

```bash
cd /tmp/secretary-voice-a-accepted/client/build/linux/x64/debug/bundle
export DISPLAY=:0
export LD_LIBRARY_PATH="$PWD/lib"
./personal_secretary
```

## Stop

Wait for **USER MANUAL ACCEPTANCE**. Do not mark PRODUCTION ACCEPTED. Do not start Voice B.
