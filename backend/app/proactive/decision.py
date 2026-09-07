from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.proactive.constants import (
    NOTIFICATION_KIND_INSIGHT,
    NOTIFICATION_KIND_TASK_PROPOSAL,
)


def _require_aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ProactiveTaskProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    start_at: datetime | None = None

    @field_validator("due_at", "start_at")
    @classmethod
    def _aware_datetimes(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value, "datetime")


class ProactiveNotificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["insight", "task_proposal"]
    title: str = Field(min_length=1, max_length=300)
    body: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "normal", "high"]
    source_object_id: UUID
    related_object_id: UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    task: ProactiveTaskProposal | None = None

    @model_validator(mode="after")
    def _kind_matches_task(self) -> Self:
        if self.kind == NOTIFICATION_KIND_INSIGHT and self.task is not None:
            raise ValueError("insight notification must not include task")
        if self.kind == NOTIFICATION_KIND_TASK_PROPOSAL and self.task is None:
            raise ValueError("task_proposal notification requires task")
        return self


class ProactiveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["none", "notify"]
    notification: ProactiveNotificationPayload | None = None

    @model_validator(mode="after")
    def _notification_matches_decision(self) -> Self:
        if self.decision == "none" and self.notification is not None:
            raise ValueError("decision=none requires notification=null")
        if self.decision == "notify" and self.notification is None:
            raise ValueError("decision=notify requires notification")
        return self
