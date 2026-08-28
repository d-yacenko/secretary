from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from app.connectors.google.constants import GMAIL_API_BASE
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.errors import GoogleApiError, GoogleConnectorError, GoogleOAuthError
from app.connectors.google.oauth_service import GoogleOAuthService, parse_token_expiry
from sqlalchemy.orm import Session


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GmailTransport:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http = http_client or httpx.Client(timeout=30.0)

    def list_message_ids(
        self,
        access_token: str,
        user_id: str,
        query: str,
        max_results: int,
    ) -> list[str]:
        response = self._http.get(
            f"{GMAIL_API_BASE}/users/{user_id}/messages",
            params={"q": query, "maxResults": max_results},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise GoogleApiError("failed to list gmail messages")
        payload = response.json()
        messages = payload.get("messages", [])
        return [str(item["id"]) for item in messages if item.get("id")]

    def get_message(self, access_token: str, user_id: str, message_id: str) -> dict[str, Any]:
        response = self._http.get(
            f"{GMAIL_API_BASE}/users/{user_id}/messages/{message_id}",
            params={"format": "full"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise GoogleApiError(f"failed to fetch gmail message {message_id}")
        return response.json()

    def fetch_account_email(self, access_token: str, user_id: str = "me") -> str:
        response = self._http.get(
            f"{GMAIL_API_BASE}/users/{user_id}/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise GoogleApiError("failed to fetch gmail profile")
        payload = response.json()
        email = payload.get("emailAddress")
        if not email:
            raise GoogleApiError("gmail profile missing email address")
        return str(email)


class GoogleTokenManager:
    def __init__(
        self,
        session: Session,
        account_store: GoogleAccountStore,
        oauth_service: GoogleOAuthService,
    ) -> None:
        self._session = session
        self._account_store = account_store
        self._oauth_service = oauth_service

    def get_valid_access_token(self, account_id: UUID, user_id: UUID) -> str:
        snapshot = self._account_store.load_credential_snapshot(account_id, user_id)
        if snapshot is None:
            raise GoogleConnectorError("google account not found")

        if (
            snapshot.access_token
            and snapshot.token_expiry
            and snapshot.token_expiry > utcnow() + timedelta(seconds=60)
        ):
            return snapshot.access_token

        if snapshot.refresh_token is None:
            raise GoogleOAuthError("google account is missing refresh token")

        self._session.commit()

        payload = self._oauth_service.refresh_access_token(snapshot.refresh_token)
        new_access = str(payload["access_token"])
        new_refresh = payload.get("refresh_token")
        new_expiry = parse_token_expiry(payload.get("expires_in"))

        account = self._account_store.get_by_id_for_user(account_id, user_id)
        if account is None:
            raise GoogleConnectorError("google account not found")
        self._account_store.update_tokens_from_refresh(
            account,
            access_token=new_access,
            refresh_token=str(new_refresh) if new_refresh else None,
            token_expiry=new_expiry,
        )
        self._session.flush()
        return new_access
