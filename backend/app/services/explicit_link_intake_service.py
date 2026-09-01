from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import DRIVE_READONLY_SCOPE, GOOGLE_DRIVE_PROVIDER
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.drive_normalize import normalize_drive_file
from app.connectors.google.drive_transport import DriveTransport
from app.connectors.google.drive_url_parser import parse_google_drive_file_id
from app.connectors.google.errors import (
    GoogleApiError,
    GoogleConfigurationError,
    GoogleConnectorError,
)
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.google.oauth_service import GoogleOAuthService
from app.connectors.yandex.constants import YANDEX_DISK_PROVIDER
from app.connectors.yandex.disk_normalize import normalize_yandex_disk_resource
from app.connectors.yandex.disk_transport import YandexDiskTransport
from app.connectors.yandex.disk_url_parser import parse_yandex_disk_share_url
from app.connectors.yandex.errors import YandexDiskApiError
from app.db.models import GoogleAccount, Object
from app.services.explicit_link_intake_errors import (
    AccountSelectionRequiredError,
    ExplicitLinkIntakeError,
)
from app.services.explicit_link_provider import detect_intake_provider
from app.services.pipeline_enqueue import enqueue_embed_object

EXPLICIT_INTAKE_MODE = "explicit_link"


@dataclass(frozen=True)
class IntakeLinkResult:
    object_id: UUID
    provider: str
    kind: str
    status: str


class ExplicitLinkIntakeService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        google_transport: DriveTransport | None = None,
        yandex_transport: YandexDiskTransport | None = None,
        account_store: GoogleAccountStore | None = None,
        token_manager: GoogleTokenManager | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._google_transport = google_transport
        self._yandex_transport = yandex_transport
        self._account_store = account_store
        self._token_manager = token_manager

    def intake_link(self, url: str, account_id: UUID | None = None) -> IntakeLinkResult:
        provider = detect_intake_provider(url)
        if provider == GOOGLE_DRIVE_PROVIDER:
            return self._intake_google_drive(url, account_id)
        if provider == YANDEX_DISK_PROVIDER:
            return self._intake_yandex_disk(url)
        raise ExplicitLinkIntakeError("unsupported link url")

    def close(self) -> None:
        if self._google_transport is not None:
            self._google_transport.close()
        if self._yandex_transport is not None:
            self._yandex_transport.close()

    def _intake_google_drive(self, url: str, account_id: UUID | None) -> IntakeLinkResult:
        if (
            self._account_store is None
            or self._token_manager is None
            or self._google_transport is None
        ):
            raise GoogleConfigurationError("google explicit link intake is not configured")

        file_id = parse_google_drive_file_id(url)
        account = self._resolve_google_account(account_id)
        self._require_drive_scope(account)

        access_token = self._token_manager.get_valid_access_token(account.id, self._user_id)
        self._session.commit()

        try:
            raw_file = self._google_transport.get_file_metadata(access_token, file_id)
        except GoogleApiError as exc:
            if exc.status_code == 404:
                raise ExplicitLinkIntakeError("google drive resource unavailable") from exc
            if exc.status_code in {401, 403}:
                raise ExplicitLinkIntakeError("google drive resource permission denied") from exc
            raise

        normalized = normalize_drive_file(
            raw_file,
            account.id,
            intake_mode=EXPLICIT_INTAKE_MODE,
        )
        if normalized is None:
            raise ExplicitLinkIntakeError("google drive resource unavailable")

        existing = self._find_existing(GOOGLE_DRIVE_PROVIDER, normalized["external_id"])
        if normalized.get("trashed"):
            if existing is None:
                raise ExplicitLinkIntakeError("google drive resource unavailable")
            internal_status = self._tombstone_existing(existing)
            return self._result(existing, internal_status)

        obj, internal_status = self._upsert(existing, normalized)
        return self._result(obj, internal_status)

    def _intake_yandex_disk(self, url: str) -> IntakeLinkResult:
        if self._yandex_transport is None:
            raise ExplicitLinkIntakeError("yandex disk intake unavailable")

        share_url = parse_yandex_disk_share_url(url)

        try:
            raw_resource = self._yandex_transport.get_public_resource_metadata(share_url)
        except YandexDiskApiError as exc:
            if exc.status_code == 404:
                raise ExplicitLinkIntakeError("yandex disk resource unavailable") from exc
            if exc.status_code in {401, 403}:
                raise ExplicitLinkIntakeError("yandex disk resource permission denied") from exc
            raise

        normalized = normalize_yandex_disk_resource(
            raw_resource,
            intake_url=share_url,
            intake_mode=EXPLICIT_INTAKE_MODE,
        )
        if normalized is None:
            raise ExplicitLinkIntakeError("yandex disk provider metadata error")

        existing = self._find_existing(YANDEX_DISK_PROVIDER, normalized["external_id"])
        obj, internal_status = self._upsert(existing, normalized)
        return self._result(obj, internal_status)

    def _resolve_google_account(self, account_id: UUID | None) -> GoogleAccount:
        assert self._account_store is not None
        if account_id is not None:
            account = self._account_store.get_by_id_for_user(account_id, self._user_id)
            if account is None:
                raise ExplicitLinkIntakeError("google account not found")
            return account

        accounts = self._account_store.list_accounts(self._user_id)
        if not accounts:
            raise ExplicitLinkIntakeError("google account not connected")

        drive_accounts = [
            account
            for account in accounts
            if DRIVE_READONLY_SCOPE in set(account.scopes or [])
        ]
        if not drive_accounts:
            raise GoogleConnectorError("google drive scope not granted")
        if len(drive_accounts) == 1:
            return drive_accounts[0]
        raise AccountSelectionRequiredError("google account selection required")

    def _require_drive_scope(self, account: GoogleAccount) -> None:
        if DRIVE_READONLY_SCOPE not in set(account.scopes or []):
            raise GoogleConnectorError("google drive scope not granted")

    def _find_existing(self, provider: str, external_id: str) -> Object | None:
        return self._session.scalar(
            select(Object).where(
                Object.user_id == self._user_id,
                Object.provider == provider,
                Object.external_id == external_id,
            )
        )

    def _upsert(self, existing: Object | None, normalized: dict[str, Any]) -> tuple[Object, str]:
        if existing is None:
            obj = Object(
                user_id=self._user_id,
                kind=normalized["kind"],
                provider=normalized["provider"],
                external_id=normalized["external_id"],
                origin=normalized["origin"],
                state=normalized["state"],
                title=normalized["title"],
                body=normalized.get("body"),
                canonical_uri=normalized.get("canonical_uri"),
                metadata_=normalized["metadata"],
                occurred_at=normalized.get("occurred_at"),
            )
            self._session.add(obj)
            self._session.flush()
            enqueue_embed_object(self._session, obj.id, self._user_id)
            return obj, "created"

        was_deleted = existing.status == "deleted"
        if not self._object_changed(existing, normalized):
            if was_deleted:
                existing.status = None
                return existing, "restored"
            return existing, "unchanged"

        semantic_changed = self._semantic_content_changed(existing, normalized)
        self._apply_normalized(existing, normalized)
        if was_deleted:
            existing.status = None
            if semantic_changed:
                enqueue_embed_object(self._session, existing.id, self._user_id)
            return existing, "restored"

        if semantic_changed:
            enqueue_embed_object(self._session, existing.id, self._user_id)
            return existing, "updated"
        return existing, "metadata_updated"

    def _tombstone_existing(self, existing: Object) -> str:
        if existing.status == "deleted":
            return "unchanged"
        existing.status = "deleted"
        return "tombstoned"

    def _result(self, obj: Object | None, internal_status: str) -> IntakeLinkResult:
        if obj is None:
            raise ExplicitLinkIntakeError("intake object unavailable")
        public_status = self._public_status(internal_status)
        return IntakeLinkResult(
            object_id=obj.id,
            provider=obj.provider,
            kind=obj.kind,
            status=public_status,
        )

    @staticmethod
    def _public_status(internal_status: str) -> str:
        if internal_status in {"created", "unchanged"}:
            return internal_status
        return "updated"

    @staticmethod
    def _object_changed(obj: Object, normalized: dict[str, Any]) -> bool:
        if obj.kind != normalized["kind"]:
            return True
        if obj.title != normalized["title"]:
            return True
        if obj.occurred_at != normalized.get("occurred_at"):
            return True
        if obj.canonical_uri != normalized.get("canonical_uri"):
            return True
        return obj.metadata_ != normalized["metadata"]

    @staticmethod
    def _semantic_content_changed(obj: Object, normalized: dict[str, Any]) -> bool:
        return obj.title != normalized["title"]

    @staticmethod
    def _apply_normalized(obj: Object, normalized: dict[str, Any]) -> None:
        obj.kind = normalized["kind"]
        obj.title = normalized["title"]
        obj.body = normalized.get("body")
        obj.canonical_uri = normalized.get("canonical_uri")
        obj.metadata_ = normalized["metadata"]
        obj.occurred_at = normalized.get("occurred_at")


def build_yandex_explicit_link_intake_service(
    session: Session,
    user_id: UUID,
    yandex_transport: YandexDiskTransport | None = None,
    http_client: Any | None = None,
) -> ExplicitLinkIntakeService:
    disk_transport = yandex_transport or YandexDiskTransport(http_client=http_client)
    return ExplicitLinkIntakeService(
        session=session,
        user_id=user_id,
        yandex_transport=disk_transport,
    )


def build_google_explicit_link_intake_service(
    session: Session,
    user_id: UUID,
    credential_key: str,
    client_file: str,
    redirect_uri: str,
    google_transport: DriveTransport | None = None,
    http_client: Any | None = None,
) -> ExplicitLinkIntakeService:
    if not credential_key:
        raise GoogleConfigurationError("credential encryption key is not configured")

    encryption = GoogleAccountStore.build_encryption(credential_key)
    account_store = GoogleAccountStore(session, encryption)
    oauth_service = GoogleOAuthService(client_file, redirect_uri, http_client=http_client)
    token_manager = GoogleTokenManager(session, account_store, oauth_service)
    drive_transport = google_transport or DriveTransport(http_client=http_client)
    return ExplicitLinkIntakeService(
        session=session,
        user_id=user_id,
        account_store=account_store,
        token_manager=token_manager,
        google_transport=drive_transport,
    )


def build_explicit_link_intake_service(
    session: Session,
    user_id: UUID,
    credential_key: str,
    client_file: str,
    redirect_uri: str,
    google_transport: DriveTransport | None = None,
    yandex_transport: YandexDiskTransport | None = None,
    http_client: Any | None = None,
) -> ExplicitLinkIntakeService:
    google_service = build_google_explicit_link_intake_service(
        session=session,
        user_id=user_id,
        credential_key=credential_key,
        client_file=client_file,
        redirect_uri=redirect_uri,
        google_transport=google_transport,
        http_client=http_client,
    )
    disk_transport = yandex_transport or YandexDiskTransport(http_client=http_client)
    return ExplicitLinkIntakeService(
        session=session,
        user_id=user_id,
        account_store=google_service._account_store,
        token_manager=google_service._token_manager,
        google_transport=google_service._google_transport,
        yandex_transport=disk_transport,
    )
