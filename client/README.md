# Personal Secretary — Flutter client

Android and Linux desktop client for Personal Secretary OS.

## Setup

```bash
cd client
flutter pub get
```

## Quality checks

```bash
flutter analyze
flutter test
```

## Run (Linux desktop)

```bash
flutter run -d linux
```

Linux builds require the desktop toolchain (`clang++`, `cmake`, `ninja`, GTK 3 dev libraries). On this development host, `flutter build linux` currently fails because CMake and related packages are not installed.

### Linux voice recording runtime

Assistant voice input on Linux uses the `record` package (6.x). The recorder prefers WAV 16 kHz mono when supported; otherwise it falls back to AAC (`m4a`) or Opus (`ogg`) with matching upload MIME types.

`record_linux` 1.x uses PulseAudio tools (not the deprecated `fmedia` binary):

- `parecord` — microphone capture (from `pulseaudio-utils`)
- `pactl` — device queries
- `ffmpeg` — encoding for non-WAV formats (AAC/Opus fallback)

On openSUSE / Fedora-style hosts:

```bash
sudo zypper install pulseaudio-utils ffmpeg
```

WAV recording needs only `parecord`; install `ffmpeg` if AAC/Opus fallback is required.

If runtime tools are missing, voice input shows a recoverable categorized error instead of crashing.

## Run (Android)

```bash
flutter run -d android
```

Debug APK build verified with:

```bash
flutter build apk --debug
```

Android voice input requires `RECORD_AUDIO` (declared in the app manifest). The `record` package handles runtime microphone permission where supported.

## Configuration

Optional default API base URL via dart-define:

```bash
flutter run -d linux --dart-define=SECRETARY_API_BASE_URL=https://your-server.example
```

The server URL is not secret. You can also enter or change it in the app setup screen. It is stored in ordinary app preferences.

## Authentication

PHASE 19.5 uses opaque bearer tokens. There is no username/password login.

1. Enter the Secretary server URL.
2. Paste a bearer token issued by the operator CLI:

   ```bash
   cd backend && python -m app.cli.auth_token issue --label operator
   ```

3. The client calls `GET /me` and only enters the app when authentication succeeds.

The bearer token is stored in platform secure storage (not SharedPreferences). Use **Forget token / disconnect this client** in Account to remove the local credential without deleting Secretary data.

Never put a real bearer token in documentation, logs, or commits.

## Manual Capture

Use the prominent **Capture** action from the app shell. Typed task text is sent to `POST /capture/task` without client-side OpenAI. Optional title, context object IDs, and dependency IDs are supported in the API contract for later UI wiring.

## Voice (PHASE 23B)

Assistant voice input records a short command to a temporary WAV file, uploads it to `POST /assistant/transcribe`, then sends the transcript through the existing Assistant message flow (`POST /assistant/message`) with the current object or notification context preserved.

Voice recordings are ephemeral temp files only. Capture-screen voice is not implemented yet.
