# Current task — Voice Assistant A R4-R3

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R3 (Android recorder truncation / audio-session corrective): implemented / awaiting Architect review and user physical gates. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED.**

R4-R3 application SHA: `d121cf90e351612275663c6845a76e9dd80ed587`

R4-R3 parent / R4-R2 docs tip: `5d3e173d9c5ba9cd99927f2ecdcaf3fa3151f3d5`

R4-R2 application SHA: `f8c9a256af9d07b77b088e94fc1110e69479343f`

R4-R1 application SHA: `e097069dad8bcb0066e531a63f5f668e786e62ab`

R4 application SHA (rejected): `a4bb618c69ff170f223bef13dd5303d8b5961b67`

**R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R3-R1 application SHA: `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

R3 application SHA (rejected by user-manual evidence): `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS. R4-R2 voice-output policy preserved.

Linux user physical launch + Voice: PASS (Architect). Android transcription physical gate: FAIL before this corrective.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not redeploy production. Do not mark R3, R4, R4-R1, R4-R2, or R4-R3 CODE ACCEPTED.

## R4-R3 facts

OpenAI rejecting <500 ms is a downstream consequence. The recorder was allowed to overlap `audioplayers` / native STREAM_MUSIC cues with an active microphone.

Sequencing now:

START: ACK → prepare mic/permissions → hands-free ready tone **completes and releases** → start recorder. Screen mic: UI/haptic only, no audible ready.

STOP: stop recorder first → optional bounded file-stabilize if the file grew → then stop/processing cue.

Zero `audioplayers` media between successful recorder start and successful recorder stop. Native hardware no longer plays a stop tone while capture is active.

500 ms WAV floor remains defensive. Debug/user-test copy includes duration: «Запись неожиданно получилась 0,32 с. Повторите попытку.»

File finalization: one 50 ms growth sample; extra wait only if the file grew; timeout 500 ms. No global trigger debounce (starting-state already ignores a second start; no duplicate-trigger proof).

R4-R2 output policy unchanged: default `handsFreeOnly`; frozen invocation source; Pending Action Plan safety.

Backend (still **not deployed**): `transcription_audio_invalid` only for locally proven short/malformed WAV; empty provider text → `transcription_unrecognized`; generic OpenAI 400 → `transcription_provider_failed`. No provider bodies.

No DB migration. Production was not mutated and not redeployed.

## Checks

- Flutter Voice / repeated-turn / cue sequencing / output-policy / hardware / lock-screen / system-assistant / short-WAV tests: **117 passed**.
- `tests/test_assistant_transcribe.py`: **16 passed**.
- `flutter analyze` on touched Dart: no new errors (pre-existing infos/warnings elsewhere).
- Android `testDebugUnitTest`: BUILD SUCCESSFUL.
- `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`.
- Linux: no plugin/RUNPATH change in this corrective; host `gstreamer-devel` still missing (classification C for host rebuild). Prior R4-R2 relocatable bundle remains the Linux launch evidence.

## Remaining USER physical gates

First smoke (not the full Samsung checklist):

1. Screen mic: speak 3–5 s; reported duration ~3–5 s; transcription succeeds.
2. Repeat screen mic three times consecutively.
3. Hardware button: speak 3–5 s; duration and transcription.
4. Two consecutive hardware turns.
5. First Assistant reply → follow-up must transcribe and be answered.

Only after these: latency / Bluetooth / full production acceptance. Prior R4-R1 Samsung / Volume Up / lock-screen items still user-run.

## Stop

Wait for **Architect review of R4-R3** and **user physical gates**. Do not mark R3, R4, R4-R1, R4-R2, or R4-R3 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.
