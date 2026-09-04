# Current task — Format Parity Pass A production verification & closure

## Status

Format Parity Pass A: **production verification complete**; **awaiting final architect closure acceptance**.

## Branch

`review/format-parity-a`

## Application SHAs

Original Format Parity A application: `5c4ca2d013946c3b904624e766b389af66021569`

Yandex storage-host corrective (architect-accepted application): `4fef52424397235d65ee8a7f0aceb25549527e6f`

Deployed VDS SHA: `4fef52424397235d65ee8a7f0aceb25549527e6f` (clean checkout)

Encrypted architect context Git blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada` (unchanged)

Alembic current/head: `0029`

`EXTRACTION_VERSION`: `format-parity-a-v1`

## VDS deploy (2026-09-04)

```bash
cd /opt/secretary
git fetch origin review/format-parity-a
git checkout review/format-parity-a
git reset --hard 4fef52424397235d65ee8a7f0aceb25549527e6f
cd infra
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
```

Post-deploy checks:

- `git rev-parse HEAD` = `4fef52424397235d65ee8a7f0aceb25549527e6f`; `git status --porcelain` empty
- Alembic current/head: `0029`
- `/health`: `{"status":"ok"}` at `http://127.0.0.1:18080/health` and `https://web-itx.duckdns.org/secretary/health`
- Worker: healthy (`infra-worker-1` Up)
- `EXTRACTION_VERSION`: `format-parity-a-v1`

## Yandex storage-host corrective smoke (post-`4fef524`)

Disposable public fixture: `verify-4fef524.ods` (`https://yadi.sk/d/08TLCPMK90SWQA`), marker `FPAPROD4FEF5244B89FB`.

| Step | Result |
|------|--------|
| Explicit intake | **200**; `content_jobs_enqueued=1` |
| Extraction job | **ran** (`extract_explicit_resource_content` done, no `untrusted_download_host`) |
| Final status | **ready** |
| `content_extraction_version` | **format-parity-a-v1** |
| Persisted representations | **4** mechanical reps with marker content |
| Blind Assistant query | **200**; answer `FPAPROD4FEF5244B89FB` |

`*.storage.yandex.net` redirect defect: **CLOSED** on deployed corrective SHA.

Object: `a04ac820-8e3f-4d3c-9336-703a5c4e0bfc`

## No automatic cloud extraction backfill

`extract_explicit_resource_content` jobs before scheduler maintenance: **15 done, 0 pending/running**

After `SourceSyncScheduler.run_maintenance()` + `trigger_all_for_user()`: **15 done, 0 pending/running**

## Focused automated tests (build host, checkout `4fef524`)

- `test_phase_29a_r1_r1_corrective.py` (Yandex download-policy / trusted-download regressions)
- `test_format_parity_a.py` + `test_phase_29a_stale_version_boundaries.py` + `test_phase_29a_r2_corrective.py` + `test_phase_29a_bounded_content_extraction.py`
- **90 passed**
- Ruff (changed backend files): **PASS**

## Prior bounded cloud E2E (pre-corrective context)

| Case | Result |
|------|--------|
| Google Drive ODT | **BLOCKED** — `drive.readonly`; upload not expanded for testing |
| Yandex Disk ODS/CSV/ODT (earlier fpaprod session) | Verified on corrective path; superseded by post-`4fef524` ODS smoke above |

## Stale-version boundary production smoke

- Routine maintenance: **no** bulk re-extract of `phase29a-v2` objects
- Explicit re-intake current-version object: **0** new extract jobs; stable object id
- Old-version disposable re-intake: **SKIPPED** (only real user spreadsheets available)

## Next

STOP — do not start Format Parity Pass B.
