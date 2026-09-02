from typing import Any
from urllib.parse import quote

import httpx

from app.connectors.google.api_errors import raise_for_google_response
from app.connectors.google.constants import DRIVE_API_BASE, DRIVE_FILE_METADATA_FIELDS


class DriveTransport:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def get_file_metadata(self, access_token: str, file_id: str) -> dict[str, Any]:
        encoded_file_id = quote(file_id, safe="")
        response = self._http.get(
            f"{DRIVE_API_BASE}/files/{encoded_file_id}",
            params={
                "fields": DRIVE_FILE_METADATA_FIELDS,
                "supportsAllDrives": "true",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "get_file_metadata")
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("drive file metadata response invalid")
        return payload
