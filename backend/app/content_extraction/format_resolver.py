"""Resolve explicit cloud resource content format and extraction eligibility."""

from pathlib import Path
from typing import Any

from app.connectors.google.constants import (
    GOOGLE_DRIVE_PROVIDER,
)
from app.connectors.yandex.constants import YANDEX_DISK_PROVIDER
from app.content_extraction.constants import SUPPORTED_BINARY_SUFFIXES

GOOGLE_APPS_DOCUMENT = "application/vnd.google-apps.document"
GOOGLE_APPS_SPREADSHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_APPS_PRESENTATION = "application/vnd.google-apps.presentation"

MIME_SUFFIX_MAP = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/x-parquet": ".parquet",
    "application/parquet": ".parquet",
}


class ContentExtractionPlan:
    def __init__(
        self,
        eligible: bool,
        status: str,
        content_format: str | None = None,
        suffix: str | None = None,
        google_export_mime: str | None = None,
    ) -> None:
        self.eligible = eligible
        self.status = status
        self.content_format = content_format
        self.suffix = suffix
        self.google_export_mime = google_export_mime


def _suffix_from_title(title: str | None) -> str:
    if not title:
        return ""
    return Path(title).suffix.lower()


def _suffix_from_metadata(metadata: dict[str, Any]) -> str:
    title_suffix = _suffix_from_title(metadata.get("filename"))
    if title_suffix:
        return title_suffix
    mime = metadata.get("mime_type")
    if mime and mime in MIME_SUFFIX_MAP:
        return MIME_SUFFIX_MAP[mime]
    return ""


def resolve_content_extraction_plan(
    provider: str,
    kind: str,
    metadata: dict[str, Any],
    title: str | None = None,
) -> ContentExtractionPlan:
    if kind == "folder":
        return ContentExtractionPlan(
            eligible=False,
            status="metadata_only",
            content_format="folder",
        )

    if provider in {GOOGLE_DRIVE_PROVIDER, "google_drive"}:
        return _resolve_google_plan(metadata, title)
    if provider in {YANDEX_DISK_PROVIDER, "yandex_disk"}:
        return _resolve_yandex_plan(metadata, title)

    return ContentExtractionPlan(eligible=False, status="unsupported")


def _resolve_google_plan(metadata: dict[str, Any], title: str | None) -> ContentExtractionPlan:
    mime = metadata.get("mime_type")
    mime_str = str(mime) if mime is not None else None

    if mime_str == GOOGLE_APPS_DOCUMENT:
        return ContentExtractionPlan(
            eligible=True,
            status="pending",
            content_format="google_docs",
            suffix=".txt",
            google_export_mime="text/plain",
        )
    if mime_str == GOOGLE_APPS_SPREADSHEET:
        return ContentExtractionPlan(
            eligible=True,
            status="pending",
            content_format="google_sheets",
            suffix=".xlsx",
            google_export_mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
    if mime_str == GOOGLE_APPS_PRESENTATION:
        return ContentExtractionPlan(
            eligible=True,
            status="pending",
            content_format="google_slides",
            suffix=".pptx",
            google_export_mime=(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
        )

    suffix = _suffix_from_title(title) or _suffix_from_metadata(metadata)
    if suffix in SUPPORTED_BINARY_SUFFIXES:
        return ContentExtractionPlan(
            eligible=True,
            status="pending",
            content_format=f"binary:{suffix}",
            suffix=suffix,
        )
    return ContentExtractionPlan(
        eligible=False,
        status="unsupported",
        content_format=mime_str or "unknown",
    )


def _resolve_yandex_plan(metadata: dict[str, Any], title: str | None) -> ContentExtractionPlan:
    if metadata.get("resource_type") == "dir":
        return ContentExtractionPlan(
            eligible=False,
            status="metadata_only",
            content_format="folder",
        )
    suffix = _suffix_from_title(title) or _suffix_from_metadata(metadata)
    if suffix in SUPPORTED_BINARY_SUFFIXES:
        return ContentExtractionPlan(
            eligible=True,
            status="pending",
            content_format=f"binary:{suffix}",
            suffix=suffix,
        )
    return ContentExtractionPlan(
        eligible=False,
        status="unsupported",
        content_format=str(metadata.get("mime_type") or "unknown"),
    )
