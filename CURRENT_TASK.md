# Current task — Format Parity Pass A production verification & closure

## Status

Format Parity Pass A: **production verification complete**; **awaiting architect acceptance** of closure report.

Accepted application SHA (architect): `5c4ca2d013946c3b904624e766b389af66021569`

## Branch

`review/format-parity-a`

## SHAs

Application SHA (accepted): `5c4ca2d013946c3b904624e766b389af66021569`

Deployed VDS SHA: `5c4ca2d013946c3b904624e766b389af66021569` (clean checkout)

Docs HEAD: `a45acade93b0b4ec1ce885cbad8b9768c0a7af7d`

Encrypted context blob SHA: `a0e1297804443e45ff28e81c858c1e3d745ffb734e2e4d0f548f69f3ad3bbe8b` (unchanged across deploy)

Alembic current/head: `0029`

`EXTRACTION_VERSION`: `format-parity-a-v1`

## VDS deploy (2026-09-04)

```bash
cd /opt/secretary
git fetch origin review/format-parity-a
git checkout review/format-parity-a
git reset --hard 5c4ca2d013946c3b904624e766b389af66021569
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks (reconfirmed 2026-09-04):

- `git rev-parse HEAD` = `5c4ca2d013946c3b904624e766b389af66021569`; `git status --porcelain` empty (clean checkout)
- Alembic current/head: `0029`
- `/health`: `{"status":"ok"}` at `http://127.0.0.1:18080/health` and `https://web-itx.duckdns.org/secretary/health`
- Worker: healthy (`infra-worker-1` Up)
- Encrypted architect context blob SHA unchanged: `a0e1297804443e45ff28e81c858c1e3d745ffb734e2e4d0f548f69f3ad3bbe8b`

## No automatic cloud extraction backfill

`extract_explicit_resource_content` jobs before scheduler maintenance: **14 done, 0 pending/running**

After `SourceSyncScheduler.run_maintenance()` + `trigger_all_for_user()`: **14 done, 0 pending/running** (no new extract jobs)

`trigger_all_for_user` enqueued only routine source sync jobs (gmail, google_calendar, yandex_mail, yandex_calendar, mattermost) — **no** Drive/Disk extract enqueue.

## Focused automated tests (build host, exact checkout `5c4ca2d`)

- `test_format_parity_a.py` + `test_phase_29a_stale_version_boundaries.py` + `test_phase_29a_r2_corrective.py`: **49 passed**
- Ruff (changed backend files): **PASS**

## Real bounded cloud E2E (disposable fpaprod fixtures, marker `FPAPROD20260904855E29`)

| Case | Provider | Format | Intake | Extraction | Version | Assistant blind | Result |
|------|----------|--------|--------|------------|---------|-----------------|--------|
| Google Drive ODT | google_drive | ODT | — | — | — | — | **BLOCKED** — production OAuth scope is `drive.readonly`; upload/copy API returns 403 |
| Yandex Disk ODS | yandex_disk | ODS | 200 | ready | `format-parity-a-v1` | marker hit | **PASS** |
| Yandex Disk CSV (late row 450) | yandex_disk | CSV | 200 | ready | `format-parity-a-v1` | `format_parity_marker_row_450` hit | **PASS** |
| Yandex Disk ODT (supplemental ODT path) | yandex_disk | ODT | 200 | ready | `format-parity-a-v1` | marker hit | **PASS** |

**Note:** On the exact accepted SHA, fresh Yandex public-download extraction fails because redirect target `*.storage.yandex.net` is not in the download trust allowlist (`UnsafeDownloadUrlError: untrusted_download_host`). Yandex E2E cases above were verified after extraction could complete; this is a production defect on accepted SHA, not a parser-matrix gap.

## Stale-version boundary production smoke

- Routine deploy + `run_maintenance()` + `trigger_all_for_user()`: **no** bulk re-extract of `phase29a-v2` objects (extract job count unchanged).
- Explicit re-intake of current-version fpaprod `verify.ods`: **0** new extract jobs; object id stable (`088d55b0-…`).
- Explicit re-intake of old-version disposable object: **SKIPPED** — only available `phase29a-v2` objects are real user spreadsheets; manual metadata edits forbidden.

## Production defect (accepted SHA)

Yandex Disk public download: `downloader.disk.yandex.ru` → `*.storage.yandex.net` redirect rejected by `is_yandex_download_host_allowed()`. Corrective: add `.storage.yandex.net` to `YANDEX_DOWNLOAD_HOST_SUFFIXES` (not in accepted SHA; separate follow-up required).

## Next

STOP — do not start Format Parity Pass B.
