# Current task — PHASE 28B-A awaiting architect review

## Status

PHASE 27C-R4C — Google Drive explicit-intake 403 corrective: **accepted / closed** at `765f79126329a26f42180d00a32fb646c6ec1598`. Deployment and real Google Drive/Sheets explicit-link E2E: **PASS**.

PHASE 28A — User Profile & Per-User Settings Foundation: **accepted / closed**. Matched-version manual E2E: **PASS**.

PHASE 28B-A — Per-User Background AI Runtime: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start 28B-B until review.

## PHASE 28B-A delivered

- Background embed / summarize / correlate jobs resolve OpenAI credential per `job.user_id`
- Reuses `EffectiveUserSettingsService` credential precedence (personal key > deployment fallback)
- Broken personal credential: no deployment/Fake fallback; job fails safely
- No global embedding client at worker startup; per-job embedding service lifetime
- Source-sync jobs unchanged; no OpenAI resolution on sync path

## Branch

`review/phase-28b-background-ai` from `765f79126329a26f42180d00a32fb646c6ec1598`.

## Not in 28B-A

- Transcription per-user migration (28B-B)
- Source sync preferences / scheduler intervals (28C)
- Flutter changes
