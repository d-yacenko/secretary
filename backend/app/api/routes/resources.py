import json
import tempfile
from pathlib import Path

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_embedding_service
from app.api.schemas import ObjectOut, ResourceRegisterOut, ResourceRegisterRequest
from app.core.config import settings
from app.core.current_user import CurrentUserContext
from app.llm.embedding_service import EmbeddingService
from app.services.errors import ConflictError, ValidationError
from app.services.job_queue_service import JobQueueService
from app.services.resource_registration_service import ResourceRegistrationService

router = APIRouter()


def _service(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> ResourceRegistrationService:
    return ResourceRegistrationService(
        session=session,
        user_id=current_user.user_id,
        job_queue=JobQueueService(session),
        embedding_service=embedding_service,
        upload_root=Path(settings.resource_upload_root),
    )


@router.post(
    "/resources/register",
    status_code=status.HTTP_201_CREATED,
    response_model=ResourceRegisterOut,
)
async def register_resource(
    request: Request,
    service: ResourceRegistrationService = Depends(_service),
) -> ResourceRegisterOut:
    content_type = request.headers.get("content-type", "")
    uploaded_path: Path | None = None
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload_raw = form.get("payload")
            if payload_raw is None:
                raise ValidationError("multipart register requires payload field")
            data = ResourceRegisterRequest.model_validate(json.loads(str(payload_raw)))
            upload = form.get("file")
            if upload is not None and hasattr(upload, "read"):
                suffix = Path(upload.filename or "upload.txt").suffix or ".txt"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(await upload.read())
                    uploaded_path = Path(tmp.name)
        else:
            body = await request.body()
            data = ResourceRegisterRequest.model_validate_json(body)

        result = service.register(data, uploaded_path=uploaded_path)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    finally:
        if uploaded_path is not None:
            uploaded_path.unlink(missing_ok=True)

    return ResourceRegisterOut(
        object_id=result.object_id,
        status=result.status,
        kind=result.kind,
        title=result.title,
        canonical_uri=result.canonical_uri,
        provider=result.provider,
        external_id=result.external_id,
        jobs_enqueued=result.jobs_enqueued,
        representations_created=result.representations_created,
    )


@router.get("/resources/{object_id}", response_model=ObjectOut)
def get_registered_resource(
    object_id: UUID,
    service: ResourceRegistrationService = Depends(_service),
) -> ObjectOut:
    from app.services.errors import NotFoundError

    try:
        obj = service.get_object_for_user(object_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.resource} not found",
        ) from exc
    return ObjectOut.from_model(obj)
