from dataclasses import dataclass
from typing import Any

import httpx

from app.connectors.google.api_errors import raise_for_google_response
from app.connectors.google.constants import (
    DRIVE_API_BASE,
    DRIVE_CHANGE_LIST_FIELDS,
    DRIVE_FILE_LIST_FIELDS,
    GOOGLE_DRIVE_DEFAULT_PAGE_SIZE,
)


@dataclass(frozen=True)
class DriveFilesPage:
    files: list[dict[str, Any]]
    next_page_token: str | None


@dataclass(frozen=True)
class DriveChangesPage:
    changes: list[dict[str, Any]]
    next_page_token: str | None
    new_start_page_token: str | None


class DriveTransport:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def get_start_page_token(self, access_token: str) -> str:
        response = self._http.get(
            f"{DRIVE_API_BASE}/changes/startPageToken",
            params={"spaces": "drive"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "get_start_page_token")
        payload = response.json()
        token = payload.get("startPageToken")
        if not token:
            raise ValueError("drive startPageToken missing")
        return str(token)

    def list_files(
        self,
        access_token: str,
        page_token: str | None,
        page_size: int,
    ) -> DriveFilesPage:
        params: dict[str, Any] = {
            "q": "trashed = false",
            "spaces": "drive",
            "pageSize": min(max(page_size, 1), GOOGLE_DRIVE_DEFAULT_PAGE_SIZE),
            "fields": DRIVE_FILE_LIST_FIELDS,
        }
        if page_token:
            params["pageToken"] = page_token
        response = self._http.get(
            f"{DRIVE_API_BASE}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "list_files")
        payload = response.json()
        files = list(payload.get("files", []))
        next_token = payload.get("nextPageToken")
        return DriveFilesPage(
            files=files,
            next_page_token=str(next_token) if next_token else None,
        )

    def list_changes(
        self,
        access_token: str,
        page_token: str,
        page_size: int,
    ) -> DriveChangesPage:
        response = self._http.get(
            f"{DRIVE_API_BASE}/changes",
            params={
                "pageToken": page_token,
                "pageSize": min(max(page_size, 1), GOOGLE_DRIVE_DEFAULT_PAGE_SIZE),
                "includeRemoved": "true",
                "spaces": "drive",
                "fields": DRIVE_CHANGE_LIST_FIELDS,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raise_for_google_response(response, "list_changes")
        payload = response.json()
        changes = list(payload.get("changes", []))
        next_token = payload.get("nextPageToken")
        new_start = payload.get("newStartPageToken")
        return DriveChangesPage(
            changes=changes,
            next_page_token=str(next_token) if next_token else None,
            new_start_page_token=str(new_start) if new_start else None,
        )
