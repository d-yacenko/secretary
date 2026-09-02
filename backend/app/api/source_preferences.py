from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.current_user import CurrentUserContext
from app.services.source_sync_preference_service import (
    EffectiveSourceSyncPreference,
    SourceSyncPreferenceService,
)
from app.source_sync.constants import SUPPORTED_SOURCE_KEYS

router = APIRouter(tags=["source-preferences"])


class EffectiveSourcePreferenceOut(BaseModel):
    source: str
    enabled: bool
    sync_interval_seconds: int
    default_sync_interval_seconds: int
    min_sync_interval_seconds: int
    max_sync_interval_seconds: int


class SourcePreferenceListOut(BaseModel):
    preferences: list[EffectiveSourcePreferenceOut]


class SourcePreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    sync_interval_seconds: int | None = None


def _serialize_preference(
    preference: EffectiveSourceSyncPreference,
) -> EffectiveSourcePreferenceOut:
    return EffectiveSourcePreferenceOut(
        source=preference.source,
        enabled=preference.enabled,
        sync_interval_seconds=preference.sync_interval_seconds,
        default_sync_interval_seconds=preference.default_sync_interval_seconds,
        min_sync_interval_seconds=preference.min_sync_interval_seconds,
        max_sync_interval_seconds=preference.max_sync_interval_seconds,
    )


@router.get("/me/source-preferences", response_model=SourcePreferenceListOut)
def list_my_source_preferences(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> SourcePreferenceListOut:
    service = SourceSyncPreferenceService.build(session)
    preferences = service.list_effective_preferences(current_user.user_id)
    return SourcePreferenceListOut(
        preferences=[_serialize_preference(item) for item in preferences]
    )


@router.patch(
    "/me/source-preferences/{source}",
    response_model=EffectiveSourcePreferenceOut,
)
def patch_my_source_preference(
    source: str,
    body: SourcePreferencePatch,
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> EffectiveSourcePreferenceOut:
    if source not in SUPPORTED_SOURCE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="unsupported source",
        )
    if not body.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no fields to update",
        )
    service = SourceSyncPreferenceService.build(session)
    try:
        preference = service.update_preference(
            current_user.user_id,
            source,
            enabled=body.enabled if "enabled" in body.model_fields_set else None,
            sync_interval_seconds=(
                body.sync_interval_seconds
                if "sync_interval_seconds" in body.model_fields_set
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _serialize_preference(preference)
