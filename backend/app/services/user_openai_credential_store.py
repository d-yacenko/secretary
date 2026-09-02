from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.connectors.google.encryption import CredentialEncryption
from app.connectors.google.errors import GoogleConfigurationError
from app.db.models import UserOpenAICredential
from app.services.user_openai_credential_errors import UserOpenAICredentialConfigurationError

MAX_OPENAI_API_KEY_LENGTH = 256


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserOpenAICredentialStore:
    def __init__(self, session: Session, encryption: CredentialEncryption | None) -> None:
        self._session = session
        self._encryption = encryption

    def get(self, user_id: UUID) -> UserOpenAICredential | None:
        return self._session.get(UserOpenAICredential, user_id)

    def is_configured(self, user_id: UUID) -> bool:
        return self.get(user_id) is not None

    def upsert(self, user_id: UUID, api_key: str) -> UserOpenAICredential:
        if self._encryption is None:
            raise UserOpenAICredentialConfigurationError(
                "credential encryption is not configured"
            )
        trimmed = api_key.strip()
        if not trimmed:
            raise ValueError("api_key cannot be blank")
        if len(trimmed) > MAX_OPENAI_API_KEY_LENGTH:
            raise ValueError("api_key exceeds maximum length")
        encrypted = self._encryption.encrypt(trimmed)
        row = self.get(user_id)
        if row is None:
            row = UserOpenAICredential(user_id=user_id, api_key_encrypted=encrypted)
            self._session.add(row)
        else:
            row.api_key_encrypted = encrypted
        row.updated_at = utcnow()
        self._session.flush()
        return row

    def delete(self, user_id: UUID) -> bool:
        row = self.get(user_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def get_api_key(self, user_id: UUID) -> str | None:
        row = self.get(user_id)
        if row is None:
            return None
        if self._encryption is None:
            raise UserOpenAICredentialConfigurationError(
                "credential encryption is not configured"
            )
        try:
            return self._encryption.decrypt(row.api_key_encrypted)
        except GoogleConfigurationError as exc:
            raise UserOpenAICredentialConfigurationError(
                "stored user OpenAI credential could not be decrypted"
            ) from exc

    @staticmethod
    def build_encryption(key: str) -> CredentialEncryption:
        try:
            return CredentialEncryption(key)
        except GoogleConfigurationError as exc:
            raise UserOpenAICredentialConfigurationError(exc.message) from exc

    @staticmethod
    def build_from_settings(session: Session) -> UserOpenAICredentialStore:
        from app.core.config import settings

        key = settings.secretary_credential_key.strip()
        encryption = None
        if key:
            encryption = UserOpenAICredentialStore.build_encryption(key)
        return UserOpenAICredentialStore(session, encryption)
