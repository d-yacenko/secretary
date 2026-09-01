# Current task — PHASE 27C-R2 awaiting architect review

## Status

PHASE 27 — Source Completion: **in progress**.

PHASE 27A — accepted / closed (`f92ca0c`).

PHASE 27B — accepted / closed (`1dc493d`).

PHASE 27C-R1 — Explicit Intake foundation + one Google Drive object: **accepted / closed** (`467332c`).

PHASE 27C-R2 — Yandex Disk explicit share-link intake: **implementation complete, awaiting architect review**.

Do **not** merge, deploy, or start Flutter paste/drop until 27C-R2 review.

## PHASE 27C-R2 delivered

- Extended `POST /intake/link` with Yandex Disk public/share link adapter
- Provider dispatch by validated URL host (no try-Google-then-Yandex)
- Yandex URL parser with host allowlist; rejects private `/client/` links
- Fixed API `GET cloud-api.yandex.net/v1/disk/public/resources` only
- One folder URL → one folder Object (no child import from `_embedded`)
- `yandex_disk` Object identity by `resource_id`; trusted OpenTarget

## Product model

Cloud/local file sources are explicit-intake resources. Connecting credentials must never imply full cloud-drive crawling. Folders are Objects themselves; children are not automatically imported.

## Superseded experiments (do not merge / deploy)

- `review/phase-27c-google-drive` (27C-A full-drive sync)
- `review/phase-27c-google-drive-ops` (27C-B recurring Drive sync)

## Not in 27C-R2

- Flutter paste/drop UX
- Local explicit intake alignment
- Yandex Disk OAuth / private objects
- Content download / summarization
- Production deploy

## Roadmap

- **27C-R2** Yandex share-link intake — awaiting review
- **27C-R3+** Flutter paste/drop, local alignment, bounded content pipeline — not started

Safe External Actions follow Source Completion.
