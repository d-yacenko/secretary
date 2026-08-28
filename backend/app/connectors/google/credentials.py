from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.google.encryption import CredentialEncryption
from app.connectors.google.errors import GoogleConfigurationError, GoogleOAuthError
from app.db.models import GoogleAccount


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GoogleAccountStore:
    def __init__(self, session: Session, encryption: CredentialEncryption) -> None:
        self._session = session
        self._encryption = encryption

    def get_by_email(self, email: str) -> GoogleAccount | None:
        return self._session.scalar(select(GoogleAccount).where(GoogleAccount.email == email))

    def get_by_id(self, account_id: UUID) -> GoogleAccount | None:
        return self._session.get(GoogleAccount, account_id)

    def list_accounts(self) -> list[GoogleAccount]:
        return list(self._session.scalars(select(GoogleAccount).order_by(GoogleAccount.email)))

    def upsert_tokens(
        self,
        email: str,
        scopes: list[str],
        access_token: str | None,
        refresh_token: str | None,
        token_expiry: datetime | None,
    ) -> GoogleAccount:
        account = self.get_by_email(email)
        if account is None:
            account = GoogleAccount(email=email, scopes=scopes)
            self._session.add(account)
        else:
            account.scopes = scopes

        if access_token is not None:
            account.access_token_encrypted = self._encryption.encrypt(access_token)
        if refresh_token is not None:
            account.refresh_token_encrypted = self._encryption.encrypt(refresh_token)
        account.token_expiry = token_expiry
        account.updated_at = utcnow()
        self._session.flush()
        return account

    def get_access_token(self, account: GoogleAccount) -> str | None:
        if account.access_token_encrypted is None:
            return None
        return self._encryption.decrypt(account.access_token_encrypted)

    def get_refresh_token(self, account: GoogleAccount) -> str | None:
        if account.refresh_token_encrypted is None:
            return None
        return self._encryption.decrypt(account.refresh_token_encrypted)

    def require_refresh_token(self, account: GoogleAccount) -> str:
        token = self.get_refresh_token(account)
        if token is None:
            raise GoogleOAuthError("google account is missing refresh token")
        return token

    def update_tokens_from_refresh(
        self,
        account: GoogleAccount,
        access_token: str,
        refresh_token: str | None,
        token_expiry: datetime | None,
    ) -> GoogleAccount:
        account.access_token_encrypted = self._encryption.encrypt(access_token)
        if refresh_token is not None:
            account.refresh_token_encrypted = self._encryption.encrypt(refresh_token)
        account.token_expiry = token_expiry
        account.updated_at = utcnow()
        self._session.flush()
        return account

    def build_encryption(key: str) -> CredentialEncryption:
        try:
            return CredentialEncryption(key)
        except GoogleConfigurationError:
            raise
