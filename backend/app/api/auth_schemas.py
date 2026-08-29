from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CAPTURE_CONTEXT_IDS = 20
MAX_CAPTURE_DEPENDS_ON_IDS = 20


class UserMeOut(BaseModel):
    id: UUID
    display_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoogleConnectionOut(BaseModel):
    connected: bool
    email: str | None = None
    gmail_available: bool = False
    calendar_available: bool = False


class YandexMailConnectionOut(BaseModel):
    connected: bool
    email: str | None = None


class YandexCalendarConnectionOut(BaseModel):
    connected: bool
    email: str | None = None


class ConnectionsOut(BaseModel):
    google: GoogleConnectionOut
    yandex_mail: YandexMailConnectionOut
    yandex_calendar: YandexCalendarConnectionOut


class CaptureTaskRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str | None = None
    context_object_ids: list[UUID] = Field(default_factory=list, max_length=MAX_CAPTURE_CONTEXT_IDS)
    depends_on_ids: list[UUID] = Field(default_factory=list, max_length=MAX_CAPTURE_DEPENDS_ON_IDS)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value


class CaptureTaskOut(BaseModel):
    task_id: UUID
    context_edge_ids: list[UUID]
    dependency_edge_ids: list[UUID]
