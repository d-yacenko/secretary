"""PHASE 26B client-assisted intake bounds."""

CLIENT_REPRESENTATION_KINDS = frozenset(
    {"full", "chunk", "schema", "sample", "statistics"}
)

TEXT_REPRESENTATION_KINDS = frozenset({"full", "chunk"})
DATASET_REPRESENTATION_KINDS = frozenset({"schema", "sample", "statistics"})

MAX_CLIENT_REPRESENTATION_PARTS = 64
MAX_CLIENT_REPRESENTATION_PART_BYTES = 16 * 1024
MAX_CLIENT_REPRESENTATION_TOTAL_BYTES = 256 * 1024
MAX_CLIENT_INTAKE_REQUEST_BYTES = 384 * 1024

CLIENT_REP_METADATA_ALLOWLIST = frozenset({"source_chunk_index"})

TEXT_FILE_SUFFIXES = frozenset({".txt", ".md"})
DATASET_FILE_SUFFIXES = frozenset({".csv"})
UNSUPPORTED_INDEX_SUFFIXES = frozenset(
    {
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".parquet",
        ".zip",
        ".gz",
        ".tar",
        ".7z",
        ".rar",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".svg",
        ".ico",
    }
)

MAX_EMAIL_ATTACHMENTS_PER_MESSAGE = 20
MAX_EMAIL_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_EMAIL_ATTACHMENT_BYTES_PER_MESSAGE = 20 * 1024 * 1024

ATTACHMENT_TEXT_SUFFIXES = frozenset({".txt", ".md", ".csv"})
