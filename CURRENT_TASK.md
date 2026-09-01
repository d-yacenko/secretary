# Current task — PHASE 27C-R4A awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — accepted / closed (`f92ca0c`).

PHASE 27B — accepted / closed (`1dc493d`).

PHASE 27C-R1 — Explicit Intake foundation + one Google Drive object: **accepted / closed** (`467332c`).

PHASE 27C-R2 — Yandex Disk explicit share-link intake: **accepted / closed** (`374db8a`).

PHASE 27C-R3 — Local explicit file/folder semantics: **accepted / closed** (`8d64f2c`).

PHASE 27C-R4A — Inbox Explicit Intake UI: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start R4B until review.

## PHASE 27C-R4A delivered

- Inbox intake bar: cloud link paste + Add; file/folder icon buttons
- `SecretaryApiClient.intakeLink()` for `POST /intake/link`
- Local file/folder pickers and Linux drag/drop via existing `LocalIntakeActions` (inbox mode)
- Explicit intake refreshes Inbox without `/sources/sync`
- Browser cloud-link drag/drop deferred to R4B

## Product model

Inbox is the primary explicit-intake boundary for cloud links and local resources. Selecting a folder does not imply importing its children.

## Branch

`review/phase-27c-inbox-explicit-intake` from `8d64f2cd907bb02f2edc1c223bba93185324d5d0`.

## Not in R4A

- Browser cloud-link drag/drop (R4B)
- Folder child import
- Content summarization
