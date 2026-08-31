from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.api.schemas import ContextItem, EdgeOut, NotificationOut, ObjectOut

MAX_CONTEXT_CHARS = 12000
DEFAULT_CONTEXT_CHARS = 8000
MAX_TASK_EVIDENCE_IDS = 8


class ToolError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    error: str | None = None


QuerySortBy = Literal[
    "due_at",
    "start_at",
    "occurred_at",
    "created_at",
    "updated_at",
    "title",
]
QuerySortOrder = Literal["asc", "desc"]


class QueryObjectsInput(BaseModel):
    kinds: list[str] = Field(default_factory=list, max_length=8)
    providers: list[str] = Field(default_factory=list, max_length=8)
    statuses: list[str] = Field(default_factory=list, max_length=8)
    states: list[str] = Field(default_factory=list, max_length=4)
    due_from: datetime | None = None
    due_to: datetime | None = None
    start_from: datetime | None = None
    start_to: datetime | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    sort_by: QuerySortBy = "created_at"
    sort_order: QuerySortOrder = "desc"
    limit: int = Field(default=20, ge=1, le=50)


class QueryObjectItemOut(BaseModel):
    object_id: UUID
    title: str
    kind: str
    provider: str | None = None
    state: str
    status: str | None = None
    due_at: datetime | None = None
    start_at: datetime | None = None
    occurred_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class QueryObjectsOutput(BaseModel):
    objects: list[QueryObjectItemOut]


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
    state: str
    status: str | None = None
    occurred_at: datetime | None = None
    relevance: float
    reasons: list[str]
    excerpt: str


class RetrieveOutput(BaseModel):
    hits: list[RetrievalHitOut]
    time_scope_used: str
    horizon_days: int | None = None
    candidate_count: int = 0
    retrieval_mode: str = "strict"
    query_atom_count: int = 0
    selected_atom_count: int = 0


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
    evidence_object_ids: list[UUID] = Field(default_factory=list, max_length=MAX_TASK_EVIDENCE_IDS)


class CreateTaskOutput(BaseModel):
    object: ObjectOut


class UpdateTaskInput(BaseModel):
    object_id: UUID
    title: str | None = Field(default=None, min_length=1)
    body: str | None = None
    due_at: datetime | None = None
    evidence_object_ids: list[UUID] = Field(default_factory=list, max_length=MAX_TASK_EVIDENCE_IDS)

    @model_validator(mode="after")
    def reject_invalid_title(self) -> Self:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title must be a non-empty string when provided")
        return self


class UpdateTaskOutput(BaseModel):
    object: ObjectOut
    changed: bool = False
    evidence_edges_created: int = 0
    evidence_added_object_ids: list[UUID] = Field(default_factory=list)
    evidence_already_linked_object_ids: list[UUID] = Field(default_factory=list)


SetTaskStatusValue = Literal["open", "in_progress", "done", "cancelled", "archived"]


class SetTaskStatusInput(BaseModel):
    object_id: UUID
    status: SetTaskStatusValue


class SetTaskStatusOutput(BaseModel):
    object: ObjectOut
    changed: bool = False
    previous_status: str | None = None
    new_status: str


class DeleteTaskInput(BaseModel):
    object_id: UUID


class DeleteTaskOutput(BaseModel):
    object: ObjectOut
    changed: bool = False
    previous_status: str | None = None
    new_status: str


class LinkObjectsInput(BaseModel):
    source_id: UUID
    target_id: UUID
    relation_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class LinkObjectsOutput(BaseModel):
    edge: EdgeOut
    created: bool = True


class GetTodayOutput(BaseModel):
    datetime: datetime
    timezone: str


class ListNotificationsInput(BaseModel):
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ListNotificationsOutput(BaseModel):
    notifications: list[NotificationOut]
