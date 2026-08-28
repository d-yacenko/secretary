from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.connectors.google.errors import GoogleConfigurationError
from app.connectors.yandex.constants import DEFAULT_IMAP_HOST, DEFAULT_IMAP_PORT
from app.connectors.yandex.credentials import YandexMailAccountStore
from app.connectors.yandex.errors import YandexConnectorError, YandexConfigurationError
from app.connectors.yandex.mail_sync import build_yandex_mail_sync_service
from app.core.config import settings
from app.core.current_user import CurrentUserContext


router = APIRouter(tags=["yandex"])


class YandexMailConnectRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    app_password: str
    imap_host: str = DEFAULT_IMAP_HOST
    imap_port: int = DEFAULT_IMAP_PORT


def _account_store(session: Session) -> YandexMailAccountStore:
    encryption = YandexMailAccountStore.build_encryption(settings.secretary_credential_key)
    return YandexMailAccountStore(session, encryption)


@router.post("/connectors/yandex/mail/connect")
def yandex_mail_connect(
    body: YandexMailConnectRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        account_store = _account_store(session)
        account = account_store.upsert_account(
            user_id=current_user.user_id,
            email=str(body.email),
            app_password=body.app_password,
            imap_host=body.imap_host,
            imap_port=body.imap_port,
        )
        session.commit()
    except (GoogleConfigurationError, YandexConfigurationError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)

    return {
        "status": "connected",
        "account_id": str(account.id),
        "email": account.email,
        "imap_host": account.imap_host,
        "imap_port": account.imap_port,
    }


@router.post("/connectors/yandex/mail/sync")
def yandex_mail_sync(
    account_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        account_store = _account_store(session)
        if account_id:
            account = account_store.get_by_id_for_user(UUID(account_id), current_user.user_id)
        else:
            accounts = account_store.list_accounts(current_user.user_id)
            account = accounts[0] if accounts else None
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="yandex mail account not found")

        sync_service = build_yandex_mail_sync_service(
            session=session,
            credential_key=settings.secretary_credential_key,
            sync_days=settings.yandex_mail_sync_days,
            default_limit=settings.yandex_mail_sync_default_limit,
            max_limit=settings.yandex_mail_sync_max_limit,
        )
        result = sync_service.sync_account(
            account.id,
            user_id=current_user.user_id,
            limit=limit,
        )
    except (GoogleConfigurationError, YandexConfigurationError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message)
    except YandexConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)

    return result
