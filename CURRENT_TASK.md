# Current task — PHASE 26B closed; wait for architect context refresh

## Status

PHASE 26B — Source Navigation, Attachments & Client-assisted File Intake: **accepted / closed** (`be6bdfa`)

PHASE 26 remains **open**.

**Do not start PHASE 26C** until architect context refresh checkpoint is complete.

## PHASE 26B accepted decisions

- Local-device mechanical extraction happens client-side where practical
- Semantic understanding remains backend-side
- Local raw files are not uploaded by default
- `.txt` / `.md` / `.csv` are client-indexable
- Unsupported formats (PDF, DOCX, XLSX, PPTX, Parquet, images, archives) are metadata-only for client-assisted intake
- Metadata-only downgrade removes old indexed content
- Gmail / Yandex attachments are canonical file objects
- `open-target` is the canonical source-navigation abstraction
- Local open actions are device-aware
- Android persistent local reopen remains deferred
- Yandex Mail uses truthful mailbox-level fallback when exact deep link cannot be derived

## PHASE 26B verification (accepted)

- full Ruff snapshot: 51 existing findings, exit 1
- `pytest`: 733 passed, 3 skipped
- `flutter analyze`: 48 info/warning, 0 errors
- `flutter test`: 249 passed
- Android APK: PASS
- Linux build: PASS
- Android `minSdk`: 23
- migrations: none
- final focused Ruff: PASS
- final focused pytest: 30 passed

## Next subphase (after architect context refresh)

PHASE 26C — Graph Topology & Search Ordering

**ARCHITECT CONTEXT REFRESH CHECKPOINT** required before implementation.
