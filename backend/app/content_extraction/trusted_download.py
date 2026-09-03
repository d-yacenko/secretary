"""SSRF-safe bounded downloads for provider-controlled URLs."""

import ipaddress
from urllib.parse import urlparse

import httpx

from app.content_extraction.bounded_download import (
    DownloadTooLargeError,
    read_bounded_response_body,
)

MAX_REDIRECT_HOPS = 5


class UnsafeDownloadUrlError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def validate_https_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise UnsafeDownloadUrlError("non_https_url")
    if not parsed.hostname:
        raise UnsafeDownloadUrlError("missing_hostname")
    if parsed.username or parsed.password:
        raise UnsafeDownloadUrlError("url_userinfo_forbidden")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost"):
        raise UnsafeDownloadUrlError("localhost_forbidden")
    _reject_private_host(host)


def _reject_private_host(host: str) -> None:
    try:
        if host.startswith("[") and host.endswith("]"):
            addr = ipaddress.ip_address(host[1:-1])
        else:
            addr = ipaddress.ip_address(host)
    except ValueError:
        return
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        raise UnsafeDownloadUrlError("private_destination_forbidden")


def bounded_get_safe_redirects(
    http: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    max_hops: int = MAX_REDIRECT_HOPS,
) -> bytes:
    validate_https_download_url(url)
    current = url
    seen: set[str] = set()
    for _ in range(max_hops + 1):
        if current in seen:
            raise UnsafeDownloadUrlError("redirect_loop")
        seen.add(current)
        response = http.get(current, follow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise UnsafeDownloadUrlError("redirect_missing_location")
            current = str(httpx.URL(current).join(location))
            validate_https_download_url(current)
            continue
        if response.status_code >= 400:
            response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                raise DownloadTooLargeError(declared, max_bytes)
        return read_bounded_response_body(response, max_bytes)
    raise UnsafeDownloadUrlError("redirect_hop_limit")
