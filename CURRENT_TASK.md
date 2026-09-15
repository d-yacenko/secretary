# Current task — Voice Assistant A R4-R4

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R4 (complete Inbox review snapshots + completion-based review marker): implemented / awaiting Architect review and user physical smoke. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED.**

R4-R4 application SHA: `dc3568d2cb2e4808f4a736933b0ce615553a11eb`

R4-R4 parent / R4-R3 docs tip / BASE: `cfab062f22f6fca9acb1d0f33b580c901f42ed3c`

R4-R3 application SHA (capture corrective physically validated by Architect): `d121cf90e351612275663c6845a76e9dd80ed587`

R4-R2 application SHA: `f8c9a256af9d07b77b088e94fc1110e69479343f`

R4-R1 application SHA: `e097069dad8bcb0066e531a63f5f668e786e62ab`

R4 application SHA (rejected): `a4bb618c69ff170f223bef13dd5303d8b5961b67`

**R4-R4 / R4-R3 / R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R3-R1 application SHA: `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

R3 application SHA (rejected by user-manual evidence): `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS (R2 no-auto-move rule refined in R4-R4, not deleted). R2-R1 reference hygiene PASS. R4-R2 voice-output policy preserved. R4-R3 capture/hardware/STT/TTS physically validated; Inbox review product defects remain until R4-R4 user smoke.

Linux user physical launch + Voice: PASS (Architect, prior). Not PRODUCTION ACCEPTED. Do not start Voice B. Do not deploy production. Do not mark R3–R4-R4 CODE ACCEPTED.

## R4-R4 facts

Hands-free Inbox review listed a first page of 20, then claimed a 20-item limit while more Telegram messages existed. After spoken review, «Просмотрено досюда» did not move.

`list_inbox_since_review_marker` now paginates a frozen snapshot (`old_marker < item <= snapshot_top`, `feed_at DESC, object_id DESC`) with an opaque continuation cursor. First page returns exact `total_count`. Typed tool `purpose`: `inspect` never yields a completion receipt; `review` may, only after the per-turn tool trace proves contiguous pagination to `has_more=false`. Receipt is server-derived, not LLM prose.

Client advances the marker only after: verified `inbox_review_receipt` + frozen turn auto-speech allowed + all TTS chunks finished without interrupt/error. Completion uses `POST /inbox/review-marker/complete` CAS (advance if current == expected anchor; already_current no-op; incompatible conflict). Arrivals above snapshot top stay new. No provider read-state mutation. No DB migration.

Inbox Conversation Compaction A is recorded as factual backlog in `DECISIONS.md` and is out of scope for this corrective.

Production was not mutated and not redeployed.

## Checks

- Backend `test_inbox_review_snapshot_r4r4.py` + `test_inbox_review_marker_assistant.py`: **34 passed**.
- Additional Voice A backend (workflow / gateway / transcribe / speech / relevance_c): **137 passed**.
- Flutter inbox-review completion + Voice capture / hardware / output-policy / lock-screen / recorder / inbox UI: **passed** (focused completion/hardware/WAV **25**; combined Voice/inbox run **89**; one crowded-run timeout flake on interrupted-preview arming reran isolated and passed).
- `flutter analyze` on touched Dart: no issues.
- Android `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`.
- Linux host rebuild: `gstreamer-1.0` / `gstreamer-devel` missing (classification C). Prior R4-R1/R4-R2 relocatable bundle remains the Linux launch evidence. Shared client API changed; this host cannot compile a Linux bundle without `gstreamer-devel`.

## Remaining USER physical smoke

1. Arrange / observe >20 new Inbox items.
2. Ask hands-free for all fresh Inbox items.
3. Secretary must know the exact total, not just page size.
4. It must continue beyond item 20.
5. Let the complete review finish speaking.
6. Inbox «Просмотрено досюда» must move to the frozen newest reviewed item.
7. Ask «что нового?» immediately: old reviewed items must not repeat.
8. Send/receive one new item after the frozen snapshot: it must still appear as new.
9. Repeat once but interrupt TTS halfway: marker must NOT move for that incomplete review.

## Stop

Wait for **Architect review of R4-R4** and **user physical smoke**. Do not mark R3, R4, R4-R1, R4-R2, R4-R3, or R4-R4 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.
