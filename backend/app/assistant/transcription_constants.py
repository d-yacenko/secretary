MAX_TRANSCRIPTION_AUDIO_BYTES = 10 * 1024 * 1024
TRANSCRIPTION_READ_CHUNK_BYTES = 65536

ALLOWED_TRANSCRIPTION_SUFFIXES = frozenset(
    {
        ".m4a",
        ".wav",
        ".webm",
        ".mp3",
        ".ogg",
        ".mp4",
        ".mpeg",
        ".mpga",
        ".oga",
        ".flac",
    }
)

AUDIO_TOO_LARGE = "audio exceeds size limit"
AUDIO_EMPTY = "audio is empty"
