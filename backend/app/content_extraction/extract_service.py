"""PHASE 29A explicit resource content extraction orchestration."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.constants import GOOGLE_DRIVE_PROVIDER
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.drive_transport import DriveTransport
from app.connectors.google.gmail_transport import GoogleTokenManager
from app.connectors.yandex.constants import YANDEX_DISK_PROVIDER
from app.connectors.yandex.disk_transport import YandexDiskTransport
from app.content_extraction.bounded_download import DownloadTooLargeError
from app.content_extraction.constants import EXTRACTION_VERSION
from app.content_extraction.format_resolver import resolve_content_extraction_plan
from app.content_extraction.google_drive_content import fetch_google_drive_content
from app.content_extraction.mechanical_extractors import extract_from_path
from app.content_extraction.mechanical_persistence import MechanicalRepresentationPersistence
from app.content_extraction.metadata_keys import (
    CONTENT_EXTRACTED_AT,
    CONTENT_EXTRACTION_ERROR,
    CONTENT_EXTRACTION_STATUS,
    CONTENT_EXTRACTION_VERSION,
    CONTENT_FORMAT,
    MECHANICAL_REPRESENTATION_COUNT,
    STATUS_FAILED,
    STATUS_READY,
    STATUS_TOO_LARGE,
    STATUS_UNSUPPORTED,
)
from app.content_extraction.revision import (
    derive_explicit_cloud_content_revision,
    metadata_extraction_version,
)
from app.content_extraction.temp_files import SecureTempFile
from app.content_extraction.yandex_disk_content import fetch_yandex_disk_public_content
from app.db.models import Object
from app.services.pipeline_enqueue import enqueue_summarize_resource
from app.services.semantic_summary_service import invalidate_semantic_summary_metadata


class ExplicitResourceContentExtractor:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        drive_transport: DriveTransport | None = None,
        yandex_transport: YandexDiskTransport | None = None,
        account_store: GoogleAccountStore | None = None,
        token_manager: GoogleTokenManager | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._drive_transport = drive_transport
        self._yandex_transport = yandex_transport
        self._account_store = account_store
        self._token_manager = token_manager
        self._persistence = MechanicalRepresentationPersistence(session)

    def close(self) -> None:
        if self._drive_transport is not None:
            self._drive_transport.close()
        if self._yandex_transport is not None:
            self._yandex_transport.close()

    def run(
        self,
        object_id: UUID,
        expected_revision: str | None,
        extraction_version: str | None,
    ) -> None:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")

        metadata = dict(obj.metadata_ or {})
        current_revision = metadata.get("content_revision")
        if expected_revision is not None and current_revision != expected_revision:
            return
        if extraction_version is not None and metadata_extraction_version(metadata) != extraction_version:
            return

        if (
            metadata.get(CONTENT_EXTRACTION_STATUS) == STATUS_READY
            and metadata_extraction_version(metadata) == EXTRACTION_VERSION
            and (current_revision == expected_revision or expected_revision is None)
        ):
            return

        plan = resolve_content_extraction_plan(
            obj.provider,
            obj.kind,
            metadata,
            obj.title,
        )
        if not plan.eligible:
            self._set_status(obj, metadata, plan.status, plan.content_format)
            return

        suffix = plan.suffix or ".bin"
        temp = SecureTempFile(suffix=suffix)
        try:
            raw = self._download_bytes(obj, metadata, plan)
            temp.write(raw)
            reps, extract_meta = extract_from_path(obj.id, temp.path)
            count = self._persistence.replace_mechanical_for_object(obj.id, reps)
            merged = invalidate_semantic_summary_metadata(metadata)
            merged.update(extract_meta)
            merged[CONTENT_EXTRACTION_STATUS] = STATUS_READY
            merged[CONTENT_EXTRACTION_VERSION] = EXTRACTION_VERSION
            merged[CONTENT_EXTRACTED_AT] = datetime.now(UTC).isoformat()
            merged[CONTENT_FORMAT] = extract_meta.get("content_format") or plan.content_format
            merged[MECHANICAL_REPRESENTATION_COUNT] = count
            merged.pop(CONTENT_EXTRACTION_ERROR, None)
            obj.metadata_ = merged
            self._session.flush()
            enqueue_summarize_resource(
                self._session,
                obj.id,
                self._user_id,
                current_revision,
            )
        except DownloadTooLargeError:
            self._fail(obj, metadata, STATUS_TOO_LARGE, "download_too_large", clear=True)
        except Exception as exc:  # noqa: BLE001
            error_code = _stable_error_code(exc)
            status = STATUS_UNSUPPORTED if error_code in {"encrypted_pdf", "unsupported_format"} else STATUS_FAILED
            self._fail(obj, metadata, status, error_code, clear=True)
        finally:
            temp.cleanup()

    def _download_bytes(
        self,
        obj: Object,
        metadata: dict[str, Any],
        plan,
    ) -> bytes:
        if obj.provider == GOOGLE_DRIVE_PROVIDER:
            if (
                self._drive_transport is None
                or self._account_store is None
                or self._token_manager is None
            ):
                raise RuntimeError("google drive extraction is not configured")
            account_id = metadata.get("account_id")
            if not account_id:
                raise ValueError("missing google account_id")
            account = self._account_store.get_by_id_for_user(UUID(str(account_id)), self._user_id)
            if account is None:
                raise ValueError("google account ownership mismatch")
            token = self._token_manager.get_valid_access_token(account.id, self._user_id)
            return fetch_google_drive_content(
                self._drive_transport,
                token,
                metadata,
                plan,
            )
        if obj.provider == YANDEX_DISK_PROVIDER:
            if self._yandex_transport is None:
                raise RuntimeError("yandex disk extraction is not configured")
            return fetch_yandex_disk_public_content(self._yandex_transport, metadata)
        raise ValueError(f"unsupported provider for extraction: {obj.provider}")

    def _set_status(
        self,
        obj: Object,
        metadata: dict[str, Any],
        status: str,
        content_format: str | None,
    ) -> None:
        merged = dict(metadata)
        merged[CONTENT_EXTRACTION_STATUS] = status
        merged[CONTENT_EXTRACTION_VERSION] = EXTRACTION_VERSION
        if content_format is not None:
            merged[CONTENT_FORMAT] = content_format
        obj.metadata_ = merged
        self._session.flush()

    def _fail(
        self,
        obj: Object,
        metadata: dict[str, Any],
        status: str,
        error_code: str,
        clear: bool,
    ) -> None:
        if clear:
            self._persistence.clear_mechanical_for_object(obj.id)
        merged = invalidate_semantic_summary_metadata(dict(metadata))
        merged[CONTENT_EXTRACTION_STATUS] = status
        merged[CONTENT_EXTRACTION_VERSION] = EXTRACTION_VERSION
        merged[CONTENT_EXTRACTION_ERROR] = error_code
        merged[CONTENT_EXTRACTED_AT] = datetime.now(UTC).isoformat()
        merged[MECHANICAL_REPRESENTATION_COUNT] = 0
        obj.metadata_ = merged
        self._session.flush()


def apply_intake_content_metadata(
    metadata: dict[str, Any],
    provider: str,
    kind: str,
    title: str | None,
) -> dict[str, Any]:
    merged = dict(metadata)
    content_revision = derive_explicit_cloud_content_revision(provider, merged)
    if content_revision is not None:
        merged["content_revision"] = content_revision
    plan = resolve_content_extraction_plan(provider, kind, merged, title)
    merged[CONTENT_EXTRACTION_STATUS] = plan.status
    merged[CONTENT_EXTRACTION_VERSION] = EXTRACTION_VERSION
    if plan.content_format is not None:
        merged[CONTENT_FORMAT] = plan.content_format
    return merged


def extraction_work_needed(
    provider: str,
    kind: str,
    title: str | None,
    prior_metadata: dict[str, Any],
    incoming_metadata: dict[str, Any],
    had_ready_mechanical: bool,
) -> bool:
    prior_revision = prior_metadata.get("content_revision")
    incoming_revision = incoming_metadata.get("content_revision")
    if incoming_revision is None:
        return False
    plan = resolve_content_extraction_plan(provider, kind, incoming_metadata, title)
    if not plan.eligible:
        return False
    if prior_revision != incoming_revision:
        return True
    if metadata_extraction_version(prior_metadata) != EXTRACTION_VERSION:
        return True
    if prior_metadata.get(CONTENT_EXTRACTION_STATUS) != STATUS_READY:
        return True
    return not had_ready_mechanical


def _stable_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, ValueError) and "encrypted" in message:
        return "encrypted_pdf"
    if "unsupported mechanical" in message:
        return "unsupported_format"
    if isinstance(exc, DownloadTooLargeError):
        return "download_too_large"
    return "extraction_failed"


def build_explicit_resource_content_extractor(
    session: Session,
    user_id: UUID,
) -> ExplicitResourceContentExtractor:
    from app.connectors.google.oauth_service import GoogleOAuthService
    from app.core.config import settings

    drive_transport = DriveTransport()
    yandex_transport = YandexDiskTransport()
    account_store = None
    token_manager = None
    if settings.secretary_credential_key:
        encryption = GoogleAccountStore.build_encryption(settings.secretary_credential_key)
        account_store = GoogleAccountStore(session, encryption)
        oauth_service = GoogleOAuthService(
            settings.google_oauth_client_file,
            settings.google_redirect_uri,
        )
        token_manager = GoogleTokenManager(session, account_store, oauth_service)

    return ExplicitResourceContentExtractor(
        session=session,
        user_id=user_id,
        drive_transport=drive_transport,
        yandex_transport=yandex_transport,
        account_store=account_store,
        token_manager=token_manager,
    )
