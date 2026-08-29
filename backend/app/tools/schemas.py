from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas import ContextItem, EdgeOut, NotificationOut, ObjectOut

MAX_CONTEXT_CHARS = 12000
DEFAULT_CONTEXT_CHARS = 8000


class ToolError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    error: str | None = None


class SearchObjectsInput(BaseModel):
    query: str = Field(min_length=1)
    kind: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchObjectsOutput(BaseModel):
    objects: list[ObjectOut]


class RetrieveInput(BaseModel):
    query: str = Field(min_length=1)
    kind: str | None = None
    time_scope: str = Field(default="auto")
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = Field(default=5, ge=1, le=5)


class RetrievalHitOut(BaseModel):
    object_id: UUID
    title: str
    kind: str
    provider: str | None = None
    occurred_at: datetime | None = None
    relevance: float
    reasons: list[str]
    excerpt: str


class RetrieveOutput(BaseModel):
    hits: list[RetrievalHitOut]
    time_scope_used: str
    horizon_days: int | None = None
    candidate_count: int = 0


class GetObjectInput(BaseModel):
    object_id: UUID


class GetObjectOutput(BaseModel):
    object: ObjectOut


class GetContextInput(BaseModel):
    object_id: UUID | None = None
    query: str | None = None
    max_chars: int = Field(default=DEFAULT_CONTEXT_CHARS, ge=1, le=MAX_CONTEXT_CHARS)


class GetContextOutput(BaseModel):
    items: list[ContextItem]
    total_chars: int
    truncated: bool


class ListNeighborsInput(BaseModel):
    object_id: UUID
    limit: int | None = Field(default=None, ge=1, le=100)


class NeighborItem(BaseModel):
    object: ObjectOut
    edge: EdgeOut
    direction: str


class ListNeighborsOutput(BaseModel):
    object_id: UUID
    neighbors: list[NeighborItem]


class CreateTaskInput(BaseModel):
    title: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    body: str | None = None
    due_at: datetime | None = None
    status: str | None = None


class CreateTaskOutput(BaseModel):
    object: ObjectOut


class UpdateTaskInput(BaseModel):
    object_id: UUID
    title: str | None = None
    body: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class UpdateTaskOutput(BaseModel):
    object: ObjectOut


class LinkObjectsInput(BaseModel):
    source_id: UUID
    target_id: UUID
    relation_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class LinkObjectsOutput(BaseModel):
    edge: EdgeOut


class GetTodayOutput(BaseModel):
    datetime: datetime
    timezone: str


class ListNotificationsInput(BaseModel):
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ListNotificationsOutput(BaseModel):
    notifications: list[NotificationOut]
