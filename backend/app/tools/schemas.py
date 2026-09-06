import re
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class RemoveRelationInput(BaseModel):
    edge_id: UUID


class RemoveRelationOutput(BaseModel):
    edge: EdgeOut
    changed: bool = False
    previous_state: str
    new_state: str


class GetTodayOutput(BaseModel):
    datetime: datetime
    timezone: str


class ListNotificationsInput(BaseModel):
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ListNotificationsOutput(BaseModel):
    notifications: list[NotificationOut]


MAX_CALENDAR_EVENT_SUMMARY_CHARS = 300
MAX_CALENDAR_EVENT_DESCRIPTION_CHARS = 4000
MAX_CALENDAR_EVENT_LOCATION_CHARS = 500


def _strip_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return value  # type: ignore[return-value]
    stripped = value.strip()
    return stripped or None


ExternalActionProvider = Literal["google", "yandex"]


def _normalize_provider(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip().lower()
        return stripped or None
    return value


class CreateCalendarEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=MAX_CALENDAR_EVENT_SUMMARY_CHARS)
    start_at: datetime
    end_at: datetime
    description: str | None = Field(default=None, max_length=MAX_CALENDAR_EVENT_DESCRIPTION_CHARS)
    location: str | None = Field(default=None, max_length=MAX_CALENDAR_EVENT_LOCATION_CHARS)
    account_email: str | None = None
    provider: ExternalActionProvider | None = None

    @field_validator("summary", mode="before")
    @classmethod
    def _strip_summary(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", "location", "account_email", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        return _normalize_provider(value)

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class CreateCalendarEventCanonicalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=MAX_CALENDAR_EVENT_SUMMARY_CHARS)
    start_at: datetime
    end_at: datetime
    description: str | None = Field(default=None, max_length=MAX_CALENDAR_EVENT_DESCRIPTION_CHARS)
    location: str | None = Field(default=None, max_length=MAX_CALENDAR_EVENT_LOCATION_CHARS)
    account_email: str = Field(min_length=1)
    calendar_id: Literal["primary"] = "primary"
    operation_id: str = Field(min_length=5, max_length=1024)
    provider: ExternalActionProvider | None = None
    calendar_href: str | None = Field(default=None, max_length=2000)
    calendar_label: str | None = Field(default=None, max_length=300)

    @field_validator("summary", "account_email", "operation_id", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", "location", "calendar_href", "calendar_label", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        return _normalize_provider(value)

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class CreateCalendarEventOutput(BaseModel):
    provider: Literal["google_calendar", "yandex_calendar"] = "google_calendar"
    account_email: str
    calendar_id: Literal["primary"] = "primary"
    event_id: str
    summary: str
    start_at: datetime
    end_at: datetime
    canonical_uri: str | None = None
    changed: bool


MAX_EMAIL_TO_RECIPIENTS = 10
MAX_EMAIL_SUBJECT_CHARS = 300
MAX_EMAIL_BODY_CHARS = 20_000
_EMAIL_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _reject_crlf(value: object, field_name: str) -> object:
    if isinstance(value, str) and ("\r" in value or "\n" in value):
        raise ValueError(f"{field_name} must not contain CR/LF")
    return value


def _normalize_email_address(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid email address")  # noqa: TRY004
    if "\r" in value or "\n" in value:
        raise ValueError("invalid email address")
    stripped = value.strip()
    if not stripped or not _EMAIL_ADDRESS_RE.match(stripped):
        raise ValueError("invalid email address")
    return stripped


class SendEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_email: str | None = None
    provider: ExternalActionProvider | None = None
    to: list[str] = Field(min_length=1, max_length=MAX_EMAIL_TO_RECIPIENTS)
    subject: str = Field(min_length=1, max_length=MAX_EMAIL_SUBJECT_CHARS)
    body: str = Field(min_length=1, max_length=MAX_EMAIL_BODY_CHARS)

    @field_validator("account_email", mode="before")
    @classmethod
    def _strip_account(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        return _normalize_provider(value)

    @field_validator("subject", mode="before")
    @classmethod
    def _subject_no_crlf(cls, value: object) -> object:
        value = _reject_crlf(value, "subject")
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("body", mode="before")
    @classmethod
    def _body_required(cls, value: object) -> object:
        if isinstance(value, str) and ("\r" in value or "\x00" in value):
            return value.replace("\r\n", "\n").replace("\r", "\n")
        return value

    @field_validator("to")
    @classmethod
    def _validate_to(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            normalized.append(_normalize_email_address(value=item))
        if not normalized:
            raise ValueError("at least one recipient is required")
        return normalized


class SendEmailCanonicalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_email: str = Field(min_length=1)
    to: list[str] = Field(min_length=1, max_length=MAX_EMAIL_TO_RECIPIENTS)
    subject: str = Field(min_length=1, max_length=MAX_EMAIL_SUBJECT_CHARS)
    body: str = Field(min_length=1, max_length=MAX_EMAIL_BODY_CHARS)
    operation_id: str = Field(min_length=5, max_length=1024)
    rfc822_message_id: str = Field(min_length=5, max_length=200)
    provider: ExternalActionProvider | None = None

    @field_validator("account_email", "operation_id", "rfc822_message_id", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        return _normalize_provider(value)

    @field_validator("subject", mode="before")
    @classmethod
    def _subject_no_crlf(cls, value: object) -> object:
        value = _reject_crlf(value, "subject")
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("to")
    @classmethod
    def _validate_to(cls, value: list[str]) -> list[str]:
        return [_normalize_email_address(item) for item in value]


class SendEmailOutput(BaseModel):
    provider: Literal["gmail", "yandex"] = "gmail"
    account_email: str
    to: list[str]
    subject: str
    provider_message_id: str | None = None
    delivery_status: Literal["sent", "already_sent", "uncertain", "failed"]
    changed: bool
    sent_copy_status: Literal["stored", "already_present", "unconfirmed"] | None = None


MAX_SCHEDULED_ACTIVITY_TITLE_CHARS = 300
MAX_SCHEDULED_ACTIVITY_BODY_CHARS = 5000
ScheduledActivityPriority = Literal["low", "normal", "high", "urgent"]
ScheduledActivityWeekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
RecurringScheduleKind = Literal["daily", "weekly"]


class CreateScheduledActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_SCHEDULED_ACTIVITY_TITLE_CHARS)
    body: str | None = Field(default=None, max_length=MAX_SCHEDULED_ACTIVITY_BODY_CHARS)
    run_at: datetime
    priority: ScheduledActivityPriority = "normal"

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("body", mode="before")
    @classmethod
    def _strip_body(cls, value: object) -> object:
        return _strip_optional_text(value)


class CreateScheduledActivityCanonicalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_SCHEDULED_ACTIVITY_TITLE_CHARS)
    body: str | None = Field(default=None, max_length=MAX_SCHEDULED_ACTIVITY_BODY_CHARS)
    run_at: datetime
    priority: ScheduledActivityPriority = "normal"

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("body", mode="before")
    @classmethod
    def _strip_body(cls, value: object) -> object:
        return _strip_optional_text(value)


class CreateScheduledActivityOutput(BaseModel):
    object: ObjectOut


class CreateRecurringScheduledActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_SCHEDULED_ACTIVITY_TITLE_CHARS)
    body: str | None = Field(default=None, max_length=MAX_SCHEDULED_ACTIVITY_BODY_CHARS)
    schedule_kind: RecurringScheduleKind
    local_time: str
    timezone: str | None = None
    weekdays: list[ScheduledActivityWeekday] | None = None
    priority: ScheduledActivityPriority = "normal"

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("body", mode="before")
    @classmethod
    def _strip_body(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("timezone", mode="before")
    @classmethod
    def _strip_timezone(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("local_time")
    @classmethod
    def _validate_local_time(cls, value: str) -> str:
        from app.domain.recurrence import parse_local_time

        try:
            parse_local_time(value)
        except ValueError as exc:
            raise ValueError("local_time must be HH:MM") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.domain.recurrence import require_iana_timezone

        try:
            return require_iana_timezone(value)
        except ValueError as exc:
            raise ValueError("invalid timezone") from exc

    @model_validator(mode="after")
    def _validate_weekdays(self) -> Self:
        from app.domain.recurrence import canonicalize_weekdays

        try:
            weekdays = canonicalize_weekdays(
                list(self.weekdays) if self.weekdays is not None else None,
                required=self.schedule_kind == "weekly",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
        if self.schedule_kind == "weekly":
            self.weekdays = list(weekdays)
        else:
            self.weekdays = None
        return self


class CreateRecurringScheduledActivityCanonicalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_SCHEDULED_ACTIVITY_TITLE_CHARS)
    body: str | None = Field(default=None, max_length=MAX_SCHEDULED_ACTIVITY_BODY_CHARS)
    schedule_kind: RecurringScheduleKind
    local_time: str
    timezone: str
    weekdays: list[ScheduledActivityWeekday] | None = None
    priority: ScheduledActivityPriority = "normal"
    run_at: datetime

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("body", mode="before")
    @classmethod
    def _strip_body(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("local_time")
    @classmethod
    def _validate_local_time(cls, value: str) -> str:
        from app.domain.recurrence import parse_local_time

        try:
            parse_local_time(value)
        except ValueError as exc:
            raise ValueError("local_time must be HH:MM") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        from app.domain.recurrence import require_iana_timezone

        try:
            return require_iana_timezone(value)
        except ValueError as exc:
            raise ValueError("invalid timezone") from exc

    @model_validator(mode="after")
    def _validate_weekdays(self) -> Self:
        from app.domain.recurrence import canonicalize_weekdays

        try:
            weekdays = canonicalize_weekdays(
                list(self.weekdays) if self.weekdays is not None else None,
                required=self.schedule_kind == "weekly",
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
        if self.schedule_kind == "weekly":
            self.weekdays = list(weekdays)
        else:
            self.weekdays = None
        return self


class CancelScheduledActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID


class CancelScheduledActivityOutput(BaseModel):
    object: ObjectOut
    changed: bool = False
    status: str
