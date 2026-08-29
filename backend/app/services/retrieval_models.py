from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RetrievalHit:
    object_id: UUID
    title: str
    kind: str
    provider: str | None
    state: str
    status: str | None
    occurred_at: datetime | None
    relevance: float
    reasons: list[str] = field(default_factory=list)
    short_excerpt: str = ""


@dataclass(frozen=True)
class RetrievalResult:
    hits: list[RetrievalHit]
    query: str
    time_scope_used: str
    horizon_days: int | None
