from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObjectCreate(BaseModel):
    kind: str
    title: str
    origin: str
    body: str | None = None
    provider: str | None = None
    external_id: str | None = None
    canonical_uri: str | None = None
    status: str | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None


class ObjectUpdate(BaseModel):
    kind: str | None = None
    title: str | None = None
    body: str | None = None
    provider: str | None = None
    external_id: str | None = None
    canonical_uri: str | None = None
    status: str | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    origin: str | None = None
    confidence: float | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field in ("kind", "title", "origin", "metadata"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
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
    metadata: dict[str, Any]
    origin: str
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
            metadata=obj.metadata_,
            origin=obj.origin,
            confidence=obj.confidence,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class EdgeCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    type: str
    origin: str
    state: str
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    representation_kind: str | None = None
    relation_type: str | None = None
    why_included: str
    canonical_uri: str | None = None


class ContextBuildResult(BaseModel):
    items: list[ContextItem]
    total_chars: int
    truncated: bool
