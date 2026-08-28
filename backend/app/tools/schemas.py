from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas import ContextItem, EdgeOut, ObjectOut

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
