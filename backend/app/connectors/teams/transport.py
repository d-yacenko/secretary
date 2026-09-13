from typing import Any, Protocol, Self
from urllib.parse import quote

import httpx

from app.connectors.teams.constants import GRAPH_API_BASE
from app.connectors.teams.errors import (
    TeamsConfigurationError,
    TeamsSecurityError,
    TeamsWriteDefiniteError,
    TeamsWriteUncertainError,
)


class TeamsTransport(Protocol):
    def get_me(self) -> dict[str, Any]:
        ...

    def list_chats(self, url: str | None = None) -> dict[str, Any]:
        ...

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        ...

    def list_chat_messages(self, chat_id: str, url: str | None = None) -> dict[str, Any]:
        ...

    def send_message(self, chat_id: str, body: str) -> dict[str, Any]:
        ...

    def reply_with_quote(self, chat_id: str, quoted_message_id: str, body: str) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class TeamsHttpTransport:
    def __init__(
        self,
        access_token: str,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        token = access_token.strip()
        if not token:
            raise TeamsConfigurationError("Teams access token is missing")
        self._access_token = token
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(follow_redirects=False, timeout=30.0)

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_me(self) -> dict[str, Any]:
        payload = self._request_json("GET", "/me")
        if not isinstance(payload, dict):
            raise TeamsConfigurationError("Microsoft Graph /me response malformed")
        return payload

    def list_chats(self, url: str | None = None) -> dict[str, Any]:
        payload = self._request_json("GET", "/me/chats", absolute_url=url)
        if not isinstance(payload, dict):
            raise TeamsConfigurationError("Microsoft Graph chats response malformed")
        return payload

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        encoded = quote(chat_id, safe="")
        payload = self._request_json("GET", f"/chats/{encoded}", params={"$expand": "members"})
        if not isinstance(payload, dict):
            raise TeamsConfigurationError("Microsoft Graph chat response malformed")
        return payload

    def list_chat_messages(self, chat_id: str, url: str | None = None) -> dict[str, Any]:
        encoded = quote(chat_id, safe="")
        payload = self._request_json(
            "GET",
            f"/chats/{encoded}/messages",
            params=None if url else {"$top": "50"},
            absolute_url=url,
        )
        if not isinstance(payload, dict):
            raise TeamsConfigurationError("Microsoft Graph chat messages response malformed")
        return payload

    def send_message(self, chat_id: str, body: str) -> dict[str, Any]:
        encoded = quote(chat_id, safe="")
        payload = self._request_write_json(
            "POST",
            f"/chats/{encoded}/messages",
            json_body={"body": {"contentType": "text", "content": body}},
        )
        if not isinstance(payload, dict):
            raise TeamsWriteUncertainError("Teams send message response malformed")
        return payload

    def reply_with_quote(self, chat_id: str, quoted_message_id: str, body: str) -> dict[str, Any]:
        encoded = quote(chat_id, safe="")
        payload = self._request_write_json(
            "POST",
            f"/chats/{encoded}/messages/replyWithQuote",
            json_body={
                "message": {"body": {"contentType": "text", "content": body}},
                "quotedMessageId": quoted_message_id,
            },
        )
        if not isinstance(payload, dict):
            raise TeamsWriteUncertainError("Teams replyWithQuote response malformed")
        return payload

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            raise TeamsSecurityError("Microsoft Graph path must be relative")
        return f"{GRAPH_API_BASE}{path}"

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        absolute_url: str | None = None,
    ) -> Any:
        url = self._absolute_or_relative(path, absolute_url)
        try:
            response = self._http_client.request(
                method, url, headers=self._headers(), params=params
            )
        except httpx.RequestError as exc:
            raise TeamsConfigurationError("Microsoft Graph request failed") from exc
        return self._parse_json(response, write=False)

    def _request_write_json(self, method: str, path: str, json_body: dict[str, Any]) -> Any:
        url = self._build_url(path)
        try:
            response = self._http_client.request(
                method, url, headers=self._headers(), json=json_body
            )
        except httpx.RequestError as exc:
            raise TeamsWriteUncertainError("Teams write request failed") from exc
        return self._parse_json(response, write=True)

    def _absolute_or_relative(self, path: str, absolute_url: str | None) -> str:
        if absolute_url:
            if not absolute_url.startswith(GRAPH_API_BASE):
                raise TeamsSecurityError("Microsoft Graph nextLink is not on graph.microsoft.com")
            return absolute_url
        return self._build_url(path)

    def _parse_json(self, response: httpx.Response, *, write: bool) -> Any:
        if 300 <= response.status_code < 400:
            if write:
                raise TeamsWriteDefiniteError("Teams redirect rejected")
            raise TeamsSecurityError("Microsoft Graph redirect rejected")
        if 400 <= response.status_code < 500:
            if write:
                raise TeamsWriteDefiniteError("Teams write rejected")
            raise TeamsConfigurationError("Microsoft Graph request rejected")
        if response.status_code >= 500:
            if write:
                raise TeamsWriteUncertainError("Teams write response uncertain")
            raise TeamsConfigurationError("Microsoft Graph request failed")
        if not response.content:
            if write:
                raise TeamsWriteUncertainError("Teams write response malformed")
            return {}
        try:
            return response.json()
        except ValueError as exc:
            if write:
                raise TeamsWriteUncertainError("Teams write response malformed") from exc
            raise TeamsConfigurationError("Microsoft Graph response malformed") from exc


class FakeTeamsTransport:
    def __init__(self) -> None:
        self.me: dict[str, Any] = {
            "id": "user-1",
            "displayName": "Secretary User",
            "userPrincipalName": "user@contoso.com",
        }
        self.chats: list[dict[str, Any]] = []
        self.messages_by_chat: dict[str, list[dict[str, Any]]] = {}
        self.send_message_calls: list[dict[str, Any]] = []
        self.reply_with_quote_calls: list[dict[str, Any]] = []
        self.send_message_response: dict[str, Any] | None = None
        self.reply_with_quote_response: dict[str, Any] | None = None
        self.send_message_error: Exception | None = None
        self.reply_with_quote_error: Exception | None = None
        self.list_chats_calls = 0
        self.list_messages_calls: list[str] = []
        self.mark_read_calls: list[str] = []

    def get_me(self) -> dict[str, Any]:
        return dict(self.me)

    def list_chats(self, url: str | None = None) -> dict[str, Any]:
        self.list_chats_calls += 1
        return {"value": [dict(chat) for chat in self.chats]}

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        for chat in self.chats:
            if chat.get("id") == chat_id:
                return dict(chat)
        return {"id": chat_id, "chatType": "oneOnOne", "members": []}

    def list_chat_messages(self, chat_id: str, url: str | None = None) -> dict[str, Any]:
        self.list_messages_calls.append(chat_id)
        return {"value": [dict(item) for item in self.messages_by_chat.get(chat_id, [])]}

    def send_message(self, chat_id: str, body: str) -> dict[str, Any]:
        payload = {"chat_id": chat_id, "body": body}
        self.send_message_calls.append(payload)
        if self.send_message_error is not None:
            raise self.send_message_error
        if self.send_message_response is not None:
            return dict(self.send_message_response)
        created = _fake_graph_message(chat_id, body, "created-compose", from_id=str(self.me.get("id")))
        self.messages_by_chat.setdefault(chat_id, []).insert(0, dict(created))
        return dict(created)

    def reply_with_quote(self, chat_id: str, quoted_message_id: str, body: str) -> dict[str, Any]:
        payload = {
            "chat_id": chat_id,
            "quoted_message_id": quoted_message_id,
            "body": body,
        }
        self.reply_with_quote_calls.append(payload)
        if self.reply_with_quote_error is not None:
            raise self.reply_with_quote_error
        if self.reply_with_quote_response is not None:
            return dict(self.reply_with_quote_response)
        created = _fake_graph_message(
            chat_id,
            body,
            "created-reply",
            from_id=str(self.me.get("id")),
            reply_to_id=quoted_message_id,
        )
        self.messages_by_chat.setdefault(chat_id, []).insert(0, dict(created))
        return dict(created)

    def close(self) -> None:
        return None


def _fake_graph_message(
    chat_id: str,
    body: str,
    message_id: str,
    *,
    from_id: str | None,
    reply_to_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "id": message_id,
        "chatId": chat_id,
        "messageType": "message",
        "createdDateTime": "2026-09-13T14:00:00Z",
        "lastModifiedDateTime": "2026-09-13T14:00:00Z",
        "from": {"user": {"id": from_id, "displayName": "Secretary User"}},
        "body": {"contentType": "text", "content": body},
    }
    if reply_to_id:
        payload["replyToId"] = reply_to_id
    return payload
