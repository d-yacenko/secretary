"""Download explicit Yandex Disk public file bytes."""

from typing import Any

from app.connectors.yandex.disk_transport import YandexDiskTransport
from app.content_extraction.constants import MAX_EXPLICIT_CLOUD_DOWNLOAD_BYTES


def fetch_yandex_disk_public_content(
    transport: YandexDiskTransport,
    metadata: dict[str, Any],
) -> bytes:
    intake_url = str(metadata.get("intake_url") or "").strip()
    if not intake_url:
        raise ValueError("missing yandex disk intake_url")
    download_url = transport.get_public_resource_download_url(intake_url)
    return transport.download_bounded_url(
        download_url,
        max_bytes=MAX_EXPLICIT_CLOUD_DOWNLOAD_BYTES,
    )
