from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_embedding_service
from app.api.schemas import (
    ObjectOut,
    TaskMutationResponse,
    TaskPatchRequest,
    TaskStatusRequest,
    TaskStatusResponse,
)
from app.core.current_user import CurrentUserContext
from app.llm.embedding_service import EmbeddingService
from app.services.errors import NotFoundError, ValidationError
from app.services.task_mutation_service import TaskMutationService

router = APIRouter()


def _service(
    session: Session = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> TaskMutationService:
    return TaskMutationService(session, current_user.user_id, embedding_service)


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{exc.resource} not found",
    )


def _validation_error(exc: ValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.message,
    )


@router.patch("/tasks/{task_id}", response_model=TaskMutationResponse)
def patch_task(
    task_id: UUID,
    data: TaskPatchRequest,
    service: TaskMutationService = Depends(_service),
) -> TaskMutationResponse:
    try:
        result = service.patch_task_fields(
            task_id,
            title=data.title if "title" in data.model_fields_set else None,
            body=data.body if "body" in data.model_fields_set else None,
            due_at=data.due_at if "due_at" in data.model_fields_set else None,
            fields_set=set(data.model_fields_set),
        )
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    return TaskMutationResponse(
        object=ObjectOut.from_model(result.object),
        changed=result.changed,
    )


@router.post("/tasks/{task_id}/status", response_model=TaskStatusResponse)
def set_task_status(
    task_id: UUID,
    data: TaskStatusRequest,
    service: TaskMutationService = Depends(_service),
) -> TaskStatusResponse:
    try:
        result = service.set_task_status(task_id, data.status)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    return TaskStatusResponse(
        object=ObjectOut.from_model(result.object),
        changed=result.changed,
        previous_status=result.previous_status,
        new_status=result.new_status,
    )


@router.delete("/tasks/{task_id}", response_model=TaskStatusResponse)
def delete_task(
    task_id: UUID,
    service: TaskMutationService = Depends(_service),
) -> TaskStatusResponse:
    try:
        result = service.soft_delete_task(task_id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    return TaskStatusResponse(
        object=ObjectOut.from_model(result.object),
        changed=result.changed,
        previous_status=result.previous_status,
        new_status=result.new_status,
    )
