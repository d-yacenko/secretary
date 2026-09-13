from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from app.connectors.teams.constants import (
    CONSUMER_TENANT_ID,
    MICROSOFT_ISSUER_PREFIX,
    MICROSOFT_ISSUER_SUFFIX,
    MICROSOFT_JWKS_URL,
)
from app.connectors.teams.errors import TeamsOAuthError
from app.connectors.teams.oauth_state import hash_oauth_secret


class TeamsJWKClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any:
        ...


@dataclass(frozen=True)
class ValidatedMicrosoftIdentity:
    tenant_id: str
    oid: str


def microsoft_issuer_for_tenant(tenant_id: str) -> str:
    return f"{MICROSOFT_ISSUER_PREFIX}{tenant_id}{MICROSOFT_ISSUER_SUFFIX}"


class MicrosoftIdTokenValidator:
    def __init__(self, jwks_client: TeamsJWKClient | None = None) -> None:
        self._jwks = jwks_client or PyJWKClient(MICROSOFT_JWKS_URL)

    def validate(
        self,
        id_token: str,
        *,
        audience: str,
        nonce_hash: str,
    ) -> ValidatedMicrosoftIdentity:
        token = id_token.strip()
        audience = audience.strip()
        nonce_hash = nonce_hash.strip()
        if not token or not audience or not nonce_hash:
            raise TeamsOAuthError("invalid Microsoft id_token")
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            key = signing_key.key if hasattr(signing_key, "key") else signing_key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=audience,
                options={
                    "require": ["exp", "aud", "iss"],
                    "verify_iss": False,
                    "verify_nbf": True,
                },
                leeway=30,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TeamsOAuthError("Microsoft id_token expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TeamsOAuthError("Microsoft id_token audience is invalid") from exc
        except jwt.InvalidTokenError as exc:
            raise TeamsOAuthError("Microsoft id_token is invalid") from exc
        if not isinstance(claims, dict):
            raise TeamsOAuthError("Microsoft id_token is invalid")
        tenant_id = str(claims.get("tid") or "").strip()
        oid = str(claims.get("oid") or "").strip()
        issuer = str(claims.get("iss") or "").strip()
        nonce = str(claims.get("nonce") or "").strip()
        if not tenant_id or not oid:
            raise TeamsOAuthError("Microsoft identity is missing tenant or user id")
        if tenant_id.lower() == CONSUMER_TENANT_ID:
            raise TeamsOAuthError("personal Microsoft accounts are not supported")
        if issuer != microsoft_issuer_for_tenant(tenant_id):
            raise TeamsOAuthError("Microsoft id_token issuer is invalid")
        if not nonce or hash_oauth_secret(nonce) != nonce_hash:
            raise TeamsOAuthError("Microsoft id_token nonce is invalid")
        return ValidatedMicrosoftIdentity(tenant_id=tenant_id, oid=oid)
