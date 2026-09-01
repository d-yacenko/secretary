# Current task — PHASE 27C-R3 awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — accepted / closed (`f92ca0c`).

PHASE 27B — accepted / closed (`1dc493d`).

PHASE 27C-R1 — Explicit Intake foundation + one Google Drive object: **accepted / closed** (`467332c`).

PHASE 27C-R2 — Yandex Disk explicit share-link intake: **accepted / closed** (`374db8aa4bf4b05e922812414e723c7f8a2c4731`).

PHASE 27C-R3 — Local explicit file/folder semantics: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start Inbox link paste/drop until 27C-R3 review.

## PHASE 27C-R3 delivered

- `POST /local/folders/client-intake` — one selected/dropped local folder → one folder Object
- Removed automatic bounded walk / child file import from explicit local folder path
- Preserved existing `POST /local/files/client-intake` single-file flow
- `folder` added to `RECENT_SOURCE_KINDS` for Inbox eligibility
- Flutter: folder pick/drop creates folder Object only; removed indexing-policy dialog

## Product model

Cloud/local file sources follow explicit-intake semantics. Connecting credentials must never imply full cloud-drive crawling. Selecting or dropping a folder creates one folder Object; children are not automatically imported.

## Superseded experiments (do not merge / deploy)

- `review/phase-27c-google-drive` (27C-A full-drive sync)
- `review/phase-27c-google-drive-ops` (27C-B recurring Drive sync)

## Not in 27C-R3

- Inbox link paste/drop UX
- Folder child import action
- Content download / summarization

## Branch

`review/phase-27c-local-explicit-intake` from `374db8aa4bf4b05e922812414e723c7f8a2c4731`.
