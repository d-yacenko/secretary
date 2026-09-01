from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.google.calendar_sync import build_calendar_sync_service
from app.connectors.google.gmail_sync import build_gmail_sync_service
from app.connectors.mattermost.sync import build_mattermost_sync_service
from app.connectors.yandex.calendar_sync import build_yandex_calendar_sync_service
from app.connectors.yandex.mail_sync import build_yandex_mail_sync_service
from app.core.config import settings


def _gmail_sync_service(session: Session):
    return build_gmail_sync_service(
        session=session,
        credential_key=settings.secretary_credential_key,
        client_file=settings.google_oauth_client_file,
        redirect_uri=settings.google_redirect_uri,
        sync_days=settings.gmail_sync_days,
        default_limit=settings.gmail_sync_default_limit,
        max_limit=settings.gmail_sync_max_limit,
    )


def _google_calendar_sync_service(session: Session):
    return build_calendar_sync_service(
        session=session,
        credential_key=settings.secretary_credential_key,
        client_file=settings.google_oauth_client_file,
        redirect_uri=settings.google_redirect_uri,
        days_back=settings.calendar_sync_days_back,
        days_forward=settings.calendar_sync_days_forward,
        default_limit=settings.calendar_sync_default_limit,
        max_limit=settings.calendar_sync_max_limit,
        max_calendars=settings.calendar_sync_max_calendars,
    )


def _yandex_mail_sync_service(session: Session):
    return build_yandex_mail_sync_service(
        session=session,
        credential_key=settings.secretary_credential_key,
        sync_days=settings.yandex_mail_sync_days,
        default_limit=settings.yandex_mail_sync_default_limit,
        max_limit=settings.yandex_mail_sync_max_limit,
    )


def _yandex_calendar_sync_service(session: Session):
    return build_yandex_calendar_sync_service(
        session=session,
        credential_key=settings.secretary_credential_key,
        days_back=settings.calendar_sync_days_back,
        days_forward=settings.calendar_sync_days_forward,
        default_limit=settings.calendar_sync_default_limit,
        max_limit=settings.calendar_sync_max_limit,
        max_calendars=settings.calendar_sync_max_calendars,
    )


def _mattermost_sync_service(session: Session):
    return build_mattermost_sync_service(
        session=session,
        credential_key=settings.secretary_credential_key,
        sync_days=settings.mattermost_sync_days,
        max_channels=settings.mattermost_sync_max_channels,
        initial_posts_per_channel=settings.mattermost_sync_initial_posts_per_channel,
        max_posts_per_run=settings.mattermost_sync_max_posts_per_run,
        overlap_seconds=settings.mattermost_sync_overlap_seconds,
    )


def handle_sync_google_gmail(
    session: Session,
    _embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    account_id = UUID(str(payload["account_id"]))
    _gmail_sync_service(session).sync_account(account_id, user_id=user_id)


def handle_sync_google_calendar(
    session: Session,
    _embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    account_id = UUID(str(payload["account_id"]))
    _google_calendar_sync_service(session).sync_account(account_id, user_id=user_id)


def handle_sync_yandex_mail(
    session: Session,
    _embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    account_id = UUID(str(payload["account_id"]))
    _yandex_mail_sync_service(session).sync_account(account_id, user_id=user_id)


def handle_sync_yandex_calendar(
    session: Session,
    _embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    account_id = UUID(str(payload["account_id"]))
    _yandex_calendar_sync_service(session).sync_account(account_id, user_id=user_id)


def handle_sync_mattermost(
    session: Session,
    _embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    account_id = UUID(str(payload["account_id"]))
    _mattermost_sync_service(session).sync_account(account_id, user_id=user_id)
