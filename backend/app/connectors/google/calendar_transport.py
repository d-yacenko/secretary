from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.connectors.google.api_errors import raise_for_google_response
from app.connectors.google.constants import CALENDAR_API_BASE


class CalendarTransport:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http = http_client or httpx.Client(timeout=30.0)

    def list_calendars(
        self,
        access_token: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        response = self._http.get(
            f"{CALENDAR_API_BASE}/users/me/calendarList",
            params={"maxResults": max_results},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "list_calendars")
        payload = response.json()
        return list(payload.get("items", []))

    def list_events(
        self,
        access_token: str,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> list[dict[str, Any]]:
        encoded_calendar_id = quote(calendar_id, safe="")
        response = self._http.get(
            f"{CALENDAR_API_BASE}/calendars/{encoded_calendar_id}/events",
            params={
                "timeMin": _format_rfc3339(time_min),
                "timeMax": _format_rfc3339(time_max),
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "list_events")
        payload = response.json()
        return list(payload.get("items", []))


def _format_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat().replace("+00:00", "Z")
