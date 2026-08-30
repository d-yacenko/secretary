from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.assistant.action_plan_constants import (
    PENDING_ACTION_PLAN_STATUS_EXPIRED,
    PENDING_ACTION_PLAN_STATUS_FAILED,
)
from app.assistant.transcription_constants import AUDIO_TOO_LARGE
from app.core.current_user import CurrentUserContext
from app.llm.assistant_models import AssistantHistoryMessage
from app.llm.openai_assistant_provider import AssistantProviderError
from app.llm.openai_transcription_provider import TranscriptionProviderError
from app.services.action_plan_service import (
    ActionPlanConflictError,
    ActionPlanService,
    PendingActionPlanView,
)
from app.services.assistant_service import (
    AssistantConfigurationError,
    AssistantProvider,
    AssistantService,
    AssistantValidationError,
    create_assistant_provider,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.transcription_service import (
    TranscriptionConfigurationError,
    TranscriptionProvider,
    create_transcription_provider,
    transcribe_audio_upload,
)

ASSISTANT_PROVIDER_UNAVAILABLE = "Assistant provider unavailable"
TRANSCRIPTION_PROVIDER_UNAVAILABLE = "Transcription provider unavailable"

router = APIRouter(tags=["assistant"])


class AssistantHistoryMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class AssistantMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    history: list[AssistantHistoryMessageIn] = Field(default_factory=list)
    context_object_id: UUID | None = None
    context_notification_id: UUID | None = None


class AssistantReferenceOut(BaseModel):
    object_id: UUID
    title: str
    kind: str
    canonical_uri: str | None = None


class AssistantAffectedObjectOut(BaseModel):
    object_id: UUID
    title: str
    kind: str
    state: str


class PendingActionOut(BaseModel):
    tool_name: str
    arguments: dict


class PendingActionPlanOut(BaseModel):
    id: UUID
    status: str
    expires_at: str
    actions: list[PendingActionOut]


class AssistantMessageResponse(BaseModel):
    answer: str
    references: list[AssistantReferenceOut]
    affected_objects: list[AssistantAffectedObjectOut]
    pending_action_plan: PendingActionPlanOut | None = None


class ActionPlanResponse(BaseModel):
    id: UUID
    status: str
    expires_at: str
    actions: list[PendingActionOut]
    result: dict | None = None
    failure: str | None = None


class AssistantTranscribeResponse(BaseModel):
    text: str


def get_assistant_provider() -> AssistantProvider:
    try:
        return create_assistant_provider()
    except AssistantConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ASSISTANT_PROVIDER_UNAVAILABLE,
        ) from exc


def get_assistant_service(
    current_user: CurrentUserContext = Depends(get_current_user),
    provider: AssistantProvider = Depends(get_assistant_provider),
) -> AssistantService:
    return AssistantService(current_user.user_id, provider)


def get_transcription_provider() -> TranscriptionProvider:
    try:
        return create_transcription_provider()
    except TranscriptionConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=TRANSCRIPTION_PROVIDER_UNAVAILABLE,
        ) from exc


def _serialize_action_plan_response(plan: PendingActionPlanView) -> ActionPlanResponse:
    return ActionPlanResponse(
        id=plan.id,
        status=plan.status,
        expires_at=plan.expires_at.isoformat(),
        actions=[
            PendingActionOut(tool_name=action["tool_name"], arguments=action["arguments"])
            for action in plan.actions
        ],
        result=plan.result,
        failure=plan.failure,
    )


@router.post("/assistant/transcribe", response_model=AssistantTranscribeResponse)
async def assistant_transcribe(
    audio: UploadFile = File(...),
    current_user: CurrentUserContext = Depends(get_current_user),
    provider: TranscriptionProvider = Depends(get_transcription_provider),
) -> AssistantTranscribeResponse:
    try:
        text = await transcribe_audio_upload(audio, provider)
    except ValidationError as exc:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.message == AUDIO_TOO_LARGE
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc
    except (TranscriptionConfigurationError, TranscriptionProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=TRANSCRIPTION_PROVIDER_UNAVAILABLE,
        ) from exc

    return AssistantTranscribeResponse(text=text)


@router.post("/assistant/message", response_model=AssistantMessageResponse)
def assistant_message(
    data: AssistantMessageRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantMessageResponse:
    history = [
        AssistantHistoryMessage(role=item.role, content=item.content)
        for item in data.history
    ]
    try:
        result = service.send_message(
            message=data.message,
            history=history,
            context_object_id=data.context_object_id,
            context_notification_id=data.context_notification_id,
        )
    except AssistantValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.resource} not found",
        ) from exc
    except (AssistantConfigurationError, AssistantProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ASSISTANT_PROVIDER_UNAVAILABLE,
        ) from exc

    pending_action_plan = None
    if result.pending_action_plan is not None:
        pending_action_plan = PendingActionPlanOut(
            id=result.pending_action_plan.id,
            status=result.pending_action_plan.status,
            expires_at=result.pending_action_plan.expires_at.isoformat(),
            actions=[
                PendingActionOut(
                    tool_name=action.tool_name,
                    arguments=action.arguments,
                )
                for action in result.pending_action_plan.actions
            ],
        )

    return AssistantMessageResponse(
        answer=result.answer,
        references=[
            AssistantReferenceOut(
                object_id=ref.object_id,
                title=ref.title,
                kind=ref.kind,
                canonical_uri=ref.canonical_uri,
            )
            for ref in result.references
        ],
        affected_objects=[
            AssistantAffectedObjectOut(
                object_id=item.object_id,
                title=item.title,
                kind=item.kind,
                state=item.state,
            )
            for item in result.affected_objects
        ],
        pending_action_plan=pending_action_plan,
    )


@router.post(
    "/assistant/action-plans/{plan_id}/approve",
    response_model=ActionPlanResponse,
)
def approve_action_plan(
    plan_id: UUID,
    response: Response,
    current_user: CurrentUserContext = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ActionPlanResponse:
    service = ActionPlanService(session, current_user.user_id)
    try:
        plan = service.approve(plan_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.resource} not found",
        ) from exc
    except ActionPlanConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc

    body = _serialize_action_plan_response(plan)
    if plan.status in (
        PENDING_ACTION_PLAN_STATUS_FAILED,
        PENDING_ACTION_PLAN_STATUS_EXPIRED,
    ):
        response.status_code = status.HTTP_409_CONFLICT
    return body


@router.post(
    "/assistant/action-plans/{plan_id}/reject",
    response_model=ActionPlanResponse,
)
def reject_action_plan(
    plan_id: UUID,
    response: Response,
    current_user: CurrentUserContext = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ActionPlanResponse:
    service = ActionPlanService(session, current_user.user_id)
    try:
        plan = service.reject(plan_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.resource} not found",
        ) from exc
    except ActionPlanConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc

    body = _serialize_action_plan_response(plan)
    if plan.status == PENDING_ACTION_PLAN_STATUS_EXPIRED:
        response.status_code = status.HTTP_409_CONFLICT
    return body
