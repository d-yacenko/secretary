from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.provenance import (
    Origin,
    State,
    default_object_state,
    validate_agent_proposal,
    validate_confidence,
    validate_origin,
    validate_state,
)


class ObjectCreate(BaseModel):
    kind: str
    title: str
    origin: Origin
    body: str | None = None
    provider: str | None = None
    external_id: str | None = None
    canonical_uri: str | None = None
    status: str | None = None
    state: State | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        validate_origin(self.origin, "object")
        state = default_object_state(self.origin, self.state)
        validate_state(state, "object")
        validate_confidence(self.confidence, "object")
        validate_agent_proposal(self.origin, state, self.confidence, "object")
        return self


class ObjectUpdate(BaseModel):
    kind: str | None = None
    title: str | None = None
    body: str | None = None
    provider: str | None = None
    external_id: str | None = None
    canonical_uri: str | None = None
    status: str | None = None
    state: State | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    confidence: float | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field in ("kind", "title", "metadata", "state"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    @model_validator(mode="after")
    def validate_confidence_range(self) -> Self:
        if "confidence" in self.model_fields_set:
            validate_confidence(self.confidence, "object")
        if self.state is not None:
            validate_state(self.state, "object")
        return self


class ObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    title: str
    body: str | None
    provider: str | None
    external_id: str | None
    canonical_uri: str | None
    status: str | None
    start_at: datetime | None
    due_at: datetime | None
    occurred_at: datetime | None
    deleted_at: datetime | None = None
    metadata: dict[str, Any]
    origin: str
    state: str
    confidence: float | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, obj: Any) -> "ObjectOut":
        return cls(
            id=obj.id,
            kind=obj.kind,
            title=obj.title,
            body=obj.body,
            provider=obj.provider,
            external_id=obj.external_id,
            canonical_uri=obj.canonical_uri,
            status=obj.status,
            start_at=obj.start_at,
            due_at=obj.due_at,
            occurred_at=obj.occurred_at,
            deleted_at=obj.deleted_at,
            metadata=obj.metadata_,
            origin=obj.origin,
            state=obj.state,
            confidence=obj.confidence,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class ObjectDeleteResponse(BaseModel):
    object_id: UUID
    deleted_at: datetime
    already_deleted: bool


class EdgeCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    type: str
    origin: Origin
    state: State
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        validate_origin(self.origin, "edge")
        validate_state(self.state, "edge")
        validate_confidence(self.confidence, "edge")
        validate_agent_proposal(self.origin, self.state, self.confidence, "edge")
        return self


class EdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    target_id: UUID
    type: str
    origin: str
    confidence: float | None
    state: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, edge: Any) -> "EdgeOut":
        return cls(
            id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            type=edge.type,
            origin=edge.origin,
            confidence=edge.confidence,
            state=edge.state,
            metadata=edge.metadata_,
            created_at=edge.created_at,
            updated_at=edge.updated_at,
        )


class NeighborOut(BaseModel):
    object: ObjectOut
    edge: EdgeOut
    direction: str


class NeighborsOut(BaseModel):
    object_id: UUID
    neighbors: list[NeighborOut]


class ContextOut(BaseModel):
    object: ObjectOut
    edges: list[EdgeOut]
    neighbors: list[ObjectOut]


class ContextItem(BaseModel):
    object_id: UUID
    kind: str
    title: str
    content: str
    origin: str
    state: str
    confidence: float | None = None
    representation_kind: str | None = None
    relation_type: str | None = None
    relation_origin: str | None = None
    relation_state: str | None = None
    relation_confidence: float | None = None
    why_included: str
    canonical_uri: str | None = None


class ContextBuildResult(BaseModel):
    items: list[ContextItem]
    total_chars: int
    truncated: bool


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str | None
    priority: str
    status: str
    source_object_id: UUID | None
    related_object_id: UUID | None
    result_object_id: UUID | None
    proposal: dict[str, Any]
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, notification: Any) -> "NotificationOut":
        return cls(
            id=notification.id,
            title=notification.title,
            body=notification.body,
            priority=notification.priority,
            status=notification.status,
            source_object_id=notification.source_object_id,
            related_object_id=notification.related_object_id,
            result_object_id=notification.result_object_id,
            proposal=notification.proposal_,
            read_at=notification.read_at,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )


class NotificationListOut(BaseModel):
    notifications: list[NotificationOut]


class TodayOut(BaseModel):
    date: str
    timezone: str
    day_start: datetime
    tasks: list[ObjectOut]
    calendar_events: list[ObjectOut]
    notifications: list[NotificationOut]


class InboxSourceObjectOut(BaseModel):
    id: UUID
    title: str
    kind: str
    provider: str | None
    origin: str
    state: str
    status: str | None
    primary_at: datetime | None
    excerpt: str | None


class SourceSyncStatusOut(BaseModel):
    source: str
    provider: str
    account_id: UUID
    account_label: str
    enabled: bool
    status: str
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    next_sync_at: datetime | None
    last_error: str | None


class InboxOut(BaseModel):
    unresolved_notifications: list[NotificationOut]
    recent_source_objects: list[InboxSourceObjectOut]
    source_sync_status: list[SourceSyncStatusOut]


class SourceStatusListOut(BaseModel):
    sources: list[SourceSyncStatusOut]


class SourceSyncTriggerOut(BaseModel):
    triggered: list[str]
    count: int


class ResourceRegisterRequest(BaseModel):
    kind: str
    title: str
    canonical_uri: str | None = None
    provider: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    local_path_metadata: dict[str, Any] | None = None
    ingest_content: bool = False


class ResourceRegisterOut(BaseModel):
    object_id: UUID
    status: str
    kind: str
    title: str
    canonical_uri: str | None
    provider: str | None
    external_id: str | None
    jobs_enqueued: int
    representations_created: int


class TaskPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1)
    body: str | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one editable field must be supplied")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null or empty")
        return self


class TaskMutationResponse(BaseModel):
    object: ObjectOut
    changed: bool


class TaskStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class TaskStatusResponse(BaseModel):
    object: ObjectOut
    changed: bool
    previous_status: str | None
    new_status: str


class SearchFacetValueOut(BaseModel):
    value: str
    count: int


class SearchFacetsOut(BaseModel):
    kinds: list[SearchFacetValueOut]
    providers: list[SearchFacetValueOut]


class GraphWorkspaceOut(BaseModel):
    root_id: UUID | None
    seed_ids: list[UUID]
    nodes: list[ObjectOut]
    edges: list[EdgeOut]
    truncated: bool


class OpenTargetOut(BaseModel):
    available: bool
    action: str
    label: str
    url: str | None = None
    device_key: str | None = None
    local_path: str | None = None
    reason: str | None = None


class RelationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    target_id: UUID
    type: str


class RelationCreateResponse(BaseModel):
    edge: EdgeOut
    created: bool


class RelationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirm", "reject"]


class RelationDecisionResponse(BaseModel):
    edge: EdgeOut
