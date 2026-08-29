PROVIDER_GOOGLE_DRIVE = "google_drive"
PROVIDER_YANDEX_DISK = "yandex_disk"
PROVIDER_UPLOAD = "upload"
PROVIDER_WEB = "web"

CLOUD_PROVIDERS = frozenset({PROVIDER_GOOGLE_DRIVE, PROVIDER_YANDEX_DISK})

REVISION_METADATA_KEYS = (
    "etag",
    "revision",
    "content_hash",
    "modified_at",
    "provider_revision",
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_WEB_FETCH_BYTES = 512_000
MAX_WEB_BODY_CHARS = 8000
WEB_FETCH_TIMEOUT_SECONDS = 15.0

ALLOWED_UPLOAD_SUFFIXES = frozenset({".txt", ".md", ".csv", ".parquet"})
