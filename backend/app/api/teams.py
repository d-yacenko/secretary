from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.connectors.teams.account_store import TeamsAccountStore
from app.connectors.teams.config import teams_is_configured
from app.connectors.teams.constants import TEAMS_OAUTH_SCOPES
from app.connectors.teams.errors import TeamsConfigurationError, TeamsConnectorError, TeamsOAuthError
from app.connectors.teams.oauth_service import (
    TeamsOAuthService,
    parse_token_expiry,
    work_school_identity_from_id_token,
)
from app.connectors.teams.oauth_state import TeamsOAuthStateService
from app.core.config import settings
from app.core.current_user import CurrentUserContext
from app.jobs.constants import JOB_TYPE_SYNC_TEAMS
from app.services.job_queue_service import JobQueueService
from app.services.source_sync_preference_service import SourceSyncPreferenceService
from app.source_sync.constants import SOURCE_TEAMS

router = APIRouter(tags=["teams"])


class TeamsAuthorizationUrlOut(BaseModel):
    authorization_url: str


def _teams_oauth_service() -> TeamsOAuthService:
    return TeamsOAuthService(
        settings.microsoft_oauth_client_id,
        settings.microsoft_oauth_client_secret,
        settings.microsoft_redirect_uri,
    )


def _account_store(session: Session) -> TeamsAccountStore:
    return TeamsAccountStore(
        session,
        TeamsAccountStore.build_encryption(settings.secretary_credential_key),
    )


def _start_teams_oauth(session: Session, user_id: UUID) -> str:
    if not teams_is_configured():
        raise TeamsConfigurationError("Microsoft Teams is not configured")
    oauth_service = _teams_oauth_service()
    state_service = TeamsOAuthStateService(session)
    state = state_service.create_state(user_id)
    session.flush()
    return oauth_service.build_authorization_url(state)


@router.post("/auth/teams/authorization-url")
def teams_oauth_authorization_url(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> TeamsAuthorizationUrlOut:
    try:
        url = _start_teams_oauth(session, current_user.user_id)
    except TeamsConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)
    return TeamsAuthorizationUrlOut(authorization_url=url)


@router.get("/auth/teams/callback")
def teams_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing oauth parameters")
    try:
        if not teams_is_configured():
            raise TeamsConfigurationError("Microsoft Teams is not configured")
        owner_user_id = TeamsOAuthStateService(session).consume_state(state)
        session.commit()
        oauth_service = _teams_oauth_service()
        token_payload = oauth_service.exchange_code(code)
        identity = work_school_identity_from_id_token(str(token_payload["id_token"]))
        granted_scope = token_payload.get("scope")
        scopes = str(granted_scope).split() if granted_scope else list(TEAMS_OAUTH_SCOPES)
        store = _account_store(session)
        account = store.upsert_tokens(
            owner_user_id,
            microsoft_user_id=identity["microsoft_user_id"],
            tenant_id=identity["tenant_id"],
            upn=identity["upn"] or None,
            display_name=identity["display_name"] or None,
            scopes=scopes,
            access_token=str(token_payload["access_token"]),
            refresh_token=str(token_payload["refresh_token"]),
            token_expiry=parse_token_expiry(token_payload.get("expires_in")),
        )
        session.commit()
        SourceSyncPreferenceService.build(session).get_effective_preference(
            owner_user_id, SOURCE_TEAMS
        )
        JobQueueService(session).ensure_recurring_source_job(
            JOB_TYPE_SYNC_TEAMS, account.id, owner_user_id
        )
        JobQueueService(session).trigger_recurring_source_job(
            owner_user_id, JOB_TYPE_SYNC_TEAMS, account.id
        )
        session.commit()
    except TeamsConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)
    except TeamsOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except TeamsConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)

    return {
        "status": "connected",
        "display_name": account.display_name,
        "upn": account.upn,
        "tenant_id": account.tenant_id,
    }
