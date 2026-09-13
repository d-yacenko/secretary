import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.connectors.teams.constants import (
    CONSUMER_TENANT_ID,
    MICROSOFT_AUTH_URL,
    MICROSOFT_TOKEN_URL,
    TEAMS_OAUTH_SCOPES,
)
from app.connectors.teams.errors import TeamsConfigurationError, TeamsOAuthError


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_token_expiry(expires_in: int | None) -> datetime | None:
    if expires_in is None:
        return None
    return utcnow() + timedelta(seconds=int(expires_in))


def decode_id_token_claims(id_token: str) -> dict[str, Any]:
    parts = id_token.split(".")
    if len(parts) < 2:
        raise TeamsOAuthError("invalid Microsoft id_token")
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TeamsOAuthError("invalid Microsoft id_token") from exc
    if not isinstance(claims, dict):
        raise TeamsOAuthError("invalid Microsoft id_token")
    return claims


def work_school_identity_from_id_token(id_token: str) -> dict[str, str]:
    claims = decode_id_token_claims(id_token)
    tenant_id = str(claims.get("tid") or "").strip()
    microsoft_user_id = str(claims.get("oid") or claims.get("sub") or "").strip()
    if not tenant_id or not microsoft_user_id:
        raise TeamsOAuthError("Microsoft identity is missing tenant or user id")
    if tenant_id.lower() == CONSUMER_TENANT_ID:
        raise TeamsOAuthError("personal Microsoft accounts are not supported")
    upn = str(claims.get("preferred_username") or claims.get("upn") or "").strip() or None
    display_name = str(claims.get("name") or "").strip() or None
    return {
        "tenant_id": tenant_id,
        "microsoft_user_id": microsoft_user_id,
        "upn": upn or "",
        "display_name": display_name or "",
    }


class TeamsOAuthService:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._redirect_uri = redirect_uri.strip()
        if not self._client_id or not self._client_secret or not self._redirect_uri:
            raise TeamsConfigurationError("Microsoft Teams OAuth is not configured")
        self._http = http_client or httpx.Client(timeout=30.0)

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": " ".join(TEAMS_OAUTH_SCOPES),
            "state": state,
            "prompt": "select_account",
        }
        return f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        response = self._http.post(
            MICROSOFT_TOKEN_URL,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(TEAMS_OAUTH_SCOPES),
            },
        )
        if response.status_code >= 400:
            raise TeamsOAuthError("failed to exchange authorization code")
        payload = response.json()
        if not isinstance(payload, dict) or "access_token" not in payload:
            raise TeamsOAuthError("token response missing access token")
        if not payload.get("refresh_token"):
            raise TeamsOAuthError("token response missing refresh token")
        if not payload.get("id_token"):
            raise TeamsOAuthError("token response missing id_token")
        return payload

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        response = self._http.post(
            MICROSOFT_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(TEAMS_OAUTH_SCOPES),
            },
        )
        if response.status_code >= 400:
            raise TeamsOAuthError("failed to refresh access token")
        payload = response.json()
        if not isinstance(payload, dict) or "access_token" not in payload:
            raise TeamsOAuthError("refresh response missing access token")
        return payload
