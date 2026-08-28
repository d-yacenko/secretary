from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.connectors.google.constants import GMAIL_API_BASE
from app.connectors.google.credentials import GoogleAccountStore
from app.connectors.google.errors import GoogleApiError, GoogleOAuthError
from app.connectors.google.oauth_service import GoogleOAuthService, parse_token_expiry
from app.db.models import GoogleAccount


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


class GoogleTokenManager:
    def __init__(
        self,
        account_store: GoogleAccountStore,
        oauth_service: GoogleOAuthService,
    ) -> None:
        self._account_store = account_store
        self._oauth_service = oauth_service

    def get_valid_access_token(self, account: GoogleAccount) -> str:
        access_token = self._account_store.get_access_token(account)
        expiry = account.token_expiry
        if access_token and expiry and expiry > utcnow() + timedelta(seconds=60):
            return access_token
        refresh_token = self._account_store.require_refresh_token(account)
        payload = self._oauth_service.refresh_access_token(refresh_token)
        new_access = str(payload["access_token"])
        new_refresh = payload.get("refresh_token")
        new_expiry = parse_token_expiry(payload.get("expires_in"))
        self._account_store.update_tokens_from_refresh(
            account,
            access_token=new_access,
            refresh_token=str(new_refresh) if new_refresh else None,
            token_expiry=new_expiry,
        )
        return new_access
