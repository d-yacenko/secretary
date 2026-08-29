"""Constants for PostgreSQL-first local retrieval (PHASE 22.5A)."""

from datetime import timedelta

TIME_SENSITIVE_SOURCE_KINDS = frozenset(
    {"email", "event", "chat_message"}
)

ANCHOR_KINDS = frozenset(
    {
        "event",
        "project",
        "task",
        "topic",
        "organization",
        "person",
        "goal",
        "course",
        "decision",
    }
)

RECENT_HORIZON_DAYS = 90
YEAR_HORIZON_DAYS = 365

MAX_CANDIDATE_POOL = 100
DEFAULT_FINAL_HITS = 5
MAX_FINAL_HITS = 20

TITLE_FTS_WEIGHT = 4.0
BODY_FTS_WEIGHT = 1.0
TRIGRAM_WEIGHT = 3.0
ANCHOR_KIND_BOOST = 0.75
RECENCY_BONUS = 0.25
RECENCY_WINDOW = timedelta(days=RECENT_HORIZON_DAYS)

STRONG_TITLE_FTS_THRESHOLD = 0.05
STRONG_TRIGRAM_THRESHOLD = 0.35
MIN_BODY_FTS_THRESHOLD = 0.02
MIN_HIT_SCORE = 0.08

SHORT_EXCERPT_MAX_CHARS = 300

TIME_SCOPE_AUTO = "auto"
TIME_SCOPE_RECENT = "recent"
TIME_SCOPE_ALL = "all"
