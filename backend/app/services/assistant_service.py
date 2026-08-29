import json
from dataclasses import dataclass
from uuid import UUID

from app.api.schemas import NotificationOut
from app.assistant.canonical_uri import sanitize_canonical_uri_for_assistant
from app.assistant.constants import (
    MAX_ASSISTANT_HISTORY_MESSAGE_CHARS,
    MAX_ASSISTANT_HISTORY_MESSAGES,
    MAX_ASSISTANT_HISTORY_TOTAL_CHARS,
    MAX_ASSISTANT_MESSAGE_CHARS,
    MAX_ASSISTANT_REFERENCES,
    MAX_UI_CONTEXT_CHARS,
)
from app.assistant.reference_ids import cap_reference_candidate_ids, dedupe_preserve_order
from app.assistant.session import run_assistant_tool
from app.assistant.tool_runner import PerTurnToolBudget
from app.core.config import settings
from app.db.session import SessionLocal
from app.llm.assistant_models import AssistantHistoryMessage, AssistantProviderResult
from app.llm.fake_assistant_provider import FakeAssistantProvider
from app.llm.openai_assistant_provider import OpenAIAssistantProvider
from app.services.errors import NotFoundError
from app.services.notification_service import NotificationService
from app.services.secretary_service import normalize_reference_datetime


@dataclass
class AssistantReference:
    object_id: UUID
    title: str
    kind: str
    canonical_uri: str | None


@dataclass
class AssistantAffectedObject:
    object_id: UUID
    title: str
    kind: str
    state: str


@dataclass
class AssistantMessageResult:
    answer: str
    references: list[AssistantReference]
    affected_objects: list[AssistantAffectedObject]


class AssistantValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AssistantProvider:
    def run(
        self,
        message: str,
        history: list[AssistantHistoryMessage],
        ui_context: str,
        reference_datetime,
        timezone: str,
        tool_runner,
    ) -> AssistantProviderResult:
        raise NotImplementedError


class AssistantService:
    def __init__(self, user_id: UUID, provider: AssistantProvider) -> None:
        self._user_id = user_id
        self._provider = provider

    def send_message(
        self,
        message: str,
        history: list[AssistantHistoryMessage],
        context_object_id: UUID | None = None,
        context_notification_id: UUID | None = None,
    ) -> AssistantMessageResult:
        normalized_message = _validate_message(message)
        normalized_history = _normalize_history(history)
        self._validate_context_ids(context_object_id, context_notification_id)
        ui_context = self._build_ui_context(context_object_id, context_notification_id)
        tz_name = settings.secretary_timezone
        reference = normalize_reference_datetime(None, tz_name)

        validated_context_ids: list[UUID] = []
        if context_object_id is not None:
            validated_context_ids.append(context_object_id)

        tool_budget = PerTurnToolBudget()

        def tool_runner(tool_name: str, arguments: dict):
            return tool_budget.run(self._user_id, tool_name, arguments)

        provider_result = self._provider.run(
            message=normalized_message,
            history=normalized_history,
            ui_context=ui_context,
            reference_datetime=reference,
            timezone=tz_name,
            tool_runner=tool_runner,
        )

        candidate_ids = cap_reference_candidate_ids(
            dedupe_preserve_order(provider_result.candidate_object_ids),
            validated_context_ids,
            MAX_ASSISTANT_REFERENCES,
        )
        affected_ids = dedupe_preserve_order(provider_result.affected_object_ids)

        references = self._serialize_references(candidate_ids)
        affected_objects = self._serialize_affected(affected_ids)
        return AssistantMessageResult(
            answer=provider_result.answer,
            references=references,
            affected_objects=affected_objects,
        )

    def _validate_context_ids(
        self,
        context_object_id: UUID | None,
        context_notification_id: UUID | None,
    ) -> None:
        if context_object_id is not None:
            result = run_assistant_tool(
                self._user_id,
                "get_object",
                {"object_id": str(context_object_id)},
            )
            if not result.success:
                raise NotFoundError("object", context_object_id)
        if context_notification_id is not None:
            session = SessionLocal()
            try:
                NotificationService(session, self._user_id).get(context_notification_id)
            finally:
                session.close()

    def _build_ui_context(
        self,
        context_object_id: UUID | None,
        context_notification_id: UUID | None,
    ) -> str:
        parts: list[str] = []
        if context_object_id is not None:
            obj_result = run_assistant_tool(
                self._user_id,
                "get_object",
                {"object_id": str(context_object_id)},
            )
            context_result = run_assistant_tool(
                self._user_id,
                "get_context",
                {
                    "object_id": str(context_object_id),
                    "max_chars": MAX_UI_CONTEXT_CHARS,
                },
            )
            if obj_result.success and obj_result.output:
                obj = obj_result.output.get("object", {})
                parts.append(
                    f"UI context object: kind={obj.get('kind')} title={obj.get('title')} "
                    f"object_id={context_object_id}"
                )
            if context_result.success and context_result.output:
                for item in context_result.output.get("items", [])[:8]:
                    excerpt = str(item.get("content", ""))[:240].replace("\n", " ")
                    parts.append(f"- {item.get('kind')} {item.get('title')}: {excerpt}")

        if context_notification_id is not None:
            session = SessionLocal()
            try:
                notification = NotificationService(session, self._user_id).get(
                    context_notification_id
                )
                notification_out = NotificationOut.from_model(notification)
            finally:
                session.close()

            parts.append(
                f"UI context notification: id={notification_out.id} "
                f"title={notification_out.title} priority={notification_out.priority}"
            )
            if notification_out.body:
                parts.append(notification_out.body[:500])
            proposal_text = json.dumps(notification_out.proposal, ensure_ascii=False)
            parts.append(f"proposal: {proposal_text[:800]}")
            if notification_out.source_object_id is not None:
                parts.append(f"source_object_id: {notification_out.source_object_id}")
            if notification_out.related_object_id is not None:
                parts.append(f"related_object_id: {notification_out.related_object_id}")

        combined = "\n".join(parts).strip()
        if len(combined) > MAX_UI_CONTEXT_CHARS:
            return combined[:MAX_UI_CONTEXT_CHARS]
        return combined

    def _serialize_references(self, candidate_ids: list[UUID]) -> list[AssistantReference]:
        references: list[AssistantReference] = []
        for object_id in candidate_ids:
            result = run_assistant_tool(
                self._user_id,
                "get_object",
                {"object_id": str(object_id)},
            )
            if not result.success or not result.output:
                continue
            obj = result.output.get("object", {})
            references.append(
                AssistantReference(
                    object_id=UUID(str(obj["id"])),
                    title=obj["title"],
                    kind=obj["kind"],
                    canonical_uri=sanitize_canonical_uri_for_assistant(obj.get("canonical_uri")),
                )
            )
        return references

    def _serialize_affected(self, affected_ids: list[UUID]) -> list[AssistantAffectedObject]:
        affected: list[AssistantAffectedObject] = []
        for object_id in affected_ids:
            result = run_assistant_tool(
                self._user_id,
                "get_object",
                {"object_id": str(object_id)},
            )
            if not result.success or not result.output:
                continue
            obj = result.output.get("object", {})
            affected.append(
                AssistantAffectedObject(
                    object_id=UUID(str(obj["id"])),
                    title=obj["title"],
                    kind=obj["kind"],
                    state=obj["state"],
                )
            )
        return affected


def _validate_message(message: str) -> str:
    trimmed = message.strip()
    if not trimmed:
        raise AssistantValidationError("message cannot be blank")
    if len(message) > MAX_ASSISTANT_MESSAGE_CHARS:
        raise AssistantValidationError("message exceeds maximum length")
    return trimmed


def _normalize_history(history: list[AssistantHistoryMessage]) -> list[AssistantHistoryMessage]:
    if len(history) > MAX_ASSISTANT_HISTORY_MESSAGES:
        raise AssistantValidationError("history exceeds maximum message count")
    normalized: list[AssistantHistoryMessage] = []
    total_chars = 0
    for item in history:
        role = item.role.strip().lower()
        if role not in ("user", "assistant"):
            raise AssistantValidationError("history role must be user or assistant")
        content = item.content.strip()
        if not content:
            raise AssistantValidationError("history message cannot be blank")
        if len(content) > MAX_ASSISTANT_HISTORY_MESSAGE_CHARS:
            raise AssistantValidationError("history message exceeds maximum length")
        total_chars += len(content)
        if total_chars > MAX_ASSISTANT_HISTORY_TOTAL_CHARS:
            raise AssistantValidationError("history exceeds maximum total length")
        normalized.append(AssistantHistoryMessage(role=role, content=content))
    return normalized


def create_assistant_provider() -> OpenAIAssistantProvider:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAIAssistantProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def create_fake_assistant_provider() -> FakeAssistantProvider:
    return FakeAssistantProvider()
