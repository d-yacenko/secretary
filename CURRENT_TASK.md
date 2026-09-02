# Current task — PHASE 27C-R4C awaiting architect review

## Status

PHASE 28A — User Profile & Per-User Settings Foundation: **accepted / closed** at `d9a7ea874379366fcacdb0646efcad871764658c`. Matched-version manual E2E: **PASS**.

PHASE 27C-R4C — Google Drive explicit-intake 403 corrective: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start 28B until review.

Google Drive 403 on real shared links is **not** claimed resolved until architect review, deploy, and real-link E2E succeed.

## PHASE 27C-R4C delivered

- `files.get` adds `supportsAllDrives=true` for Shared Drive metadata
- Google Drive metadata errors classified by HTTP status + reason (not all 401/403 → permission denied)
- External Google authorization failures → controlled intake 400 (`google drive authorization requires reconnect`); **not** Secretary HTTP 401 / logout
- Deployment/API configuration 403 → `GoogleConfigurationError` → HTTP 503
- Sanitized diagnostics: operation, status, reason (no tokens or raw auth headers)

## Architectural rule (unchanged)

One pasted Google Drive URL → one `files.get` → one Object. No `files.list`, no sync, no recursive folder import.

## Branch

`review/phase-27c-google-drive-403` from `bc5a7d29976482bca033543c49a04f9b51f974d0`.

## Not in 27C-R4C

- Embedding / transcription / background AI migration (28B)
- Source sync preferences (28C)
- Flutter redesign beyond existing Inbox error display
