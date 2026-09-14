# Current task — Voice Assistant A R4-R2

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R2 (hands-free output policy + mobile transcription root-cause/fix): implemented / awaiting Architect review and user physical gates. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED.**

R4-R2 application SHA: `f8c9a256af9d07b77b088e94fc1110e69479343f`

R4-R2 parent (docs tip / branch tip at R4-R2 start): `4108e202407b54b8e4ad529567572907e6cee500`

R4-R1 application SHA: `e097069dad8bcb0066e531a63f5f668e786e62ab`

R4 application SHA (rejected): `a4bb618c69ff170f223bef13dd5303d8b5961b67`

**R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R3-R1 application SHA: `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

R3 application SHA (rejected by user-manual evidence): `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not redeploy production. Do not mark R3, R4, R4-R1, or R4-R2 CODE ACCEPTED.

## R4-R2 facts

Invocation source is typed: `typed` | `screenMic` | `hardwareButton` | `systemAssistant`. Frozen at recording start. A later stop gesture does not change it.

Local per-user SharedPreferences `voice_output_policy.$userId`: `handsFreeOnly` (default) / `allVoiceInput` / `never`. Not synced to UserSettings. Account radios «Автоозвучивание ответов» on Android and Linux.

Default matrix: typed never speaks; screen mic is text-only; hardware / system / lock-screen assistant auto-speak. Changing the pref mid-turn does not alter the frozen turn.

If auto-speech is not allowed: Pending Action Plan stays visual; no narration; affirmative «Да» stays unarmed / fail-closed; exact «Нет» may still reject; visual approve/reject keep existing lock-screen restrictions.

`audioplayers` uses the default `AudioPlayer` / USAGE_MEDIA. No custom Bluetooth stack. Physical Bluetooth routing left for user acceptance.

Production transcription diagnosis (read-only, SHA `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`, model `gpt-4o-mini-transcribe`, phone user has a personal OpenAI credential): Linux/long WAVs succeed; phone-sized 80–400 ms PCM WAVs (2604–12844 bytes, `secretary_voice.wav` / `audio/wav`) were collapsed into HTTP 502 `"Transcription provider unavailable"` after OpenAI 400 / empty text. Not wrong base URL, not missing credential, not missing model. Encoder was not changed.

Client: structurally inspect WAV; reject clips shorter than 500 ms locally with Russian copy; debug-log encoder/filename/MIME/bytes/duration/API base URL/HTTP status (no token/audio/transcript). Screen mic and hardware share the same transcription pipeline.

Backend (not deployed): typed `{code,message}` — `transcription_provider_not_configured` / `transcription_provider_failed` (502) and `transcription_audio_invalid` (422). No provider bodies or secrets.

No DB migration. Production was not mutated and not redeployed.

## Checks

- `dart format` on R4-R2 Dart files: clean.
- Flutter Voice A / output-policy / hardware / lock-screen / system-assistant / bootstrap / shell / short-WAV tests: passed.
- `tests/test_assistant_transcribe.py`: **14 passed**.
- Android `testDebugUnitTest`: BUILD SUCCESSFUL (native contract tests unchanged).
- `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`.
- Linux debug bundle built in Tumbleweed container; host launch without `LD_LIBRARY_PATH`: `env -u LD_LIBRARY_PATH /tmp/secretary-linux-r4r2-bundle/personal_secretary` (timeout after Dart VM start). Host `flutter build linux` still needs `gstreamer-devel` (classification C).

## Remaining USER physical gates

- Phone: same short harmless phrase through on-screen mic **and** hardware button after this client.
- Screen-mic + default policy: textual Assistant answer, **no** `/assistant/speech`.
- Three short real turns with latency marks once transcription works, including `speech_rtt_ms` only when `autoSpeechAllowed=true`.
- Bluetooth media route while a headset is active.
- Prior R4-R1 Samsung / Volume Up / lock-screen items still user-run.

## Stop

Wait for **Architect review of R4-R2** and **user physical gates**. Do not mark R3, R4, R4-R1, or R4-R2 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.
