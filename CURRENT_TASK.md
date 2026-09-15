# Current task — Voice Assistant A R4-R4-R1

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R4-R1 (chronological Inbox review order): implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.**

R4-R4-R1 application SHA: `0ab2cb6f1ae2a373f8b719314777824434c9adda`

R4-R4-R1 parent / R4-R4 docs tip: `c4bcd66020d747668eb99ea03ea7613814e4b8d8`

R4-R4 application SHA (not deployed; do not deploy): `dc3568d2cb2e4808f4a736933b0ce615553a11eb`

R4-R3 application SHA (capture corrective physically validated by Architect): `d121cf90e351612275663c6845a76e9dd80ed587`

**R4-R4-R1 / R4-R4 / R4-R3 / R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R1 PASS. R2 marker architecture PASS (auto-move refined in R4-R4). R2-R1 reference hygiene PASS. R4-R2 output policy preserved. R4-R3 capture physically validated. Inbox Conversation Compaction A remains backlog / not started.

Do not start Voice B. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## R4-R4-R1 facts

Spoken `purpose=review` previously traversed newest → oldest. Review now freezes `snapshot_top` as the newest eligible object strictly newer than the marker, then paginates the frozen window oldest → newest (`feed_at ASC, object_id ASC`). Continuation is strictly newer than last emitted, still `<= snapshot_top`. `inspect` stays newest-first. Inbox UI / `list_page` unchanged.

Opaque cursor is v=2 with `dir` (`asc` review / `desc` inspect). v=1 and direction/purpose mismatch fail closed. `total_count` remains exact; review `remaining_count` is items strictly newer than last emitted. Verified receipt / CAS completion still advances to frozen newest `snapshot_top` after complete playback. No DB migration. Production not mutated.

## Checks

- Backend `test_inbox_review_snapshot_r4r4.py` + `test_inbox_review_marker_assistant.py`: **36 passed**.
- Voice A speech / transcribe / tool gateway / relevance_c: **88 passed**.
- Flutter `inbox_review_completion_test`: **11 passed**. Recorder screen-mic ready-cue test passed isolated; crowded-file run had one flake (pre-existing, no Dart change).
- `ruff check` on touched backend files: clean.
- Android APK not rebuilt: no shared Dart/client API change (cursor remains opaque).
- Linux: no Dart change; host `gstreamer-devel` still missing (classification C).

## Remaining

Architect review of R4-R4-R1. After PASS, deploy **this** application SHA, not `dc3568d2`. Then user physical smoke including chronological Telegram/email narration (oldest → newest, including across page 20).

## Stop

Wait for Architect. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.
