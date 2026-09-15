# Current task — Voice Assistant A R4-R4-R2

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R4-R2 (on-screen microphone strictly silent-output): implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.**

R4-R4-R2 application SHA: `276fe709527a7d300660cbe444ae40ee520e7e05`

R4-R4-R2 parent / previous docs tip: `09f58b9ebf261df728352faf239ff2759cf12031`

R4-R4-R1 application SHA (chronological Inbox review; backend unchanged; do not deploy yet): `0ab2cb6f1ae2a373f8b719314777824434c9adda`

R4-R4 application SHA (not deployed; do not deploy): `dc3568d2cb2e4808f4a736933b0ce615553a11eb`

R4-R3 application SHA (capture corrective physically validated by Architect): `d121cf90e351612275663c6845a76e9dd80ed587`

**R4-R4-R2 / R4-R4-R1 / R4-R4 / R4-R3 / R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R1 PASS. R2 marker architecture PASS (auto-move refined in R4-R4). R2-R1 reference hygiene PASS. R4-R2 output policy refined in R4-R4-R2: screen mic is dictation-only. R4-R3 capture physically validated. Inbox Conversation Compaction A remains backlog / not started.

Do not start Voice B. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## R4-R4-R2 facts

Client-only. `VoiceInvocationSource.screenMic` always freezes `autoSpeechAllowed=false` on Linux and Android; no local setting can re-enable screen-mic TTS. Typed remains silent. Hands-free sources (`hardwareButton`, `systemAssistant`, including lock-screen) auto-speak only when the local policy is `handsFreeEnabled` (default). `allVoiceInput` is removed. Stored `all_voice_input` and `hands_free_only` decode and rewrite to `hands_free_enabled`; `never` stays `never`. Account/Profile shows a two-state switch «Озвучивать ответы в hands-free режиме». Screen-mic Inbox review may display a receipt but must not auto-complete the marker. Screen-mic Pending Action Plan is visual-only; affirmative «Да» stays unarmed unless the frozen plan was fully narrated in hands-free. Source freeze unchanged. Backend R4-R4-R1 chronological review is untouched. No DB migration. Production not mutated.

## Checks

- Flutter Voice A + R4-R4 marker completion + account policy: **127 passed**.
- `flutter analyze` on touched Dart: clean.
- Android debug APK rebuilt: `sdkVersion:'23'`.
- Linux: host `gstreamer-devel` still missing (classification C); no Linux rebuild/launch on this host.

## Remaining

Architect review of R4-R4-R2 application SHA `276fe709527a7d300660cbe444ae40ee520e7e05`. After PASS, Architect issues the exact-SHA deploy command. Manual smoke after that deploy: PC and Android on-screen mic → text only, zero auto-speech (including devices that previously stored `all_voice_input`); Android Volume Up hands-free → spoken when hands-free speech is enabled.

## Stop

Wait for Architect. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.
