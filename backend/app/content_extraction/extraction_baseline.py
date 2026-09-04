"""Deterministic extraction source baseline for worker authority checks."""

import hashlib
from typing import Any

from app.content_extraction.constants import EXTRACTION_VERSION
from app.content_extraction.revision import derive_web_remote_content_revision
from app.resources.constants import PROVIDER_WEB

EXTRACTION_BASELINE_METADATA_KEY = "extraction_baseline"


def derive_web_extraction_baseline(metadata: dict[str, Any]) -> str:
    remote = derive_web_remote_content_revision(metadata)
    parts = [
        str(metadata.get("final_url") or ""),
        str(metadata.get("detected_suffix") or ""),
        str(metadata.get("content_length") if metadata.get("content_length") is not None else ""),
        str(metadata.get("content_format") or ""),
        remote or "no-remote-rev",
        EXTRACTION_VERSION,
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]
    return f"web:baseline:{digest}"


def derive_extraction_baseline(provider: str, metadata: dict[str, Any]) -> str | None:
    if provider in {PROVIDER_WEB, "web"}:
        return derive_web_extraction_baseline(metadata)
    return None


def worker_extraction_authoritative(
    *,
    provider: str,
    metadata: dict[str, Any],
    expected_revision: str | None,
    expected_baseline: str | None,
) -> bool:
    if expected_revision is not None and metadata.get("content_revision") != expected_revision:
        return False
    if expected_baseline is not None and provider in {PROVIDER_WEB, "web"}:
        current = derive_web_extraction_baseline(metadata)
        if current != expected_baseline:
            return False
    return True
