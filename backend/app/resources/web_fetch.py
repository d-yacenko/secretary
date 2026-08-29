import ipaddress
import re
import socket
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx

from app.resources.constants import (
    MAX_WEB_BODY_CHARS,
    MAX_WEB_FETCH_BYTES,
    MAX_WEB_REDIRECTS,
    REDIRECT_STATUS_CODES,
    WEB_FETCH_TIMEOUT_SECONDS,
)


class WebFetchError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class WebFetchResult:
    title: str | None
    text: str
    final_url: str


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified:
        return True
    if ip.is_multicast:
        return True
    if hasattr(ip, "is_global") and not ip.is_global:
        return True
    return False


def _hostname_literal_blocked(hostname: str) -> bool:
    lowered = hostname.lower().rstrip(".")
    if lowered in {"localhost", "0.0.0.0"} or lowered.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return _ip_is_blocked(hostname)


def _resolve_host_ips(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebFetchError("web url host resolution failed") from exc
    if not infos:
        raise WebFetchError("web url host resolution failed")
    return [info[4][0] for info in infos]


def _validate_url_target(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise WebFetchError("web url must use http or https")
    hostname = parsed.hostname
    if not hostname:
        raise WebFetchError("web url hostname missing")
    if _hostname_literal_blocked(hostname):
        raise WebFetchError("web url host is not allowed")
    for resolved_ip in _resolve_host_ips(hostname):
        if _ip_is_blocked(resolved_ip):
            raise WebFetchError("web url host is not allowed")
    return url.strip()


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title or None


def _extract_text(html: str) -> str:
    stripped = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
    text = unescape(re.sub(r"\s+", " ", stripped)).strip()
    if len(text) > MAX_WEB_BODY_CHARS:
        return text[:MAX_WEB_BODY_CHARS]
    return text


def _read_response_body(response: httpx.Response) -> str:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > MAX_WEB_FETCH_BYTES:
            raise WebFetchError("web fetch exceeded size limit")
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def fetch_web_page(url: str) -> WebFetchResult:
    current_url = _validate_url_target(url)
    with httpx.Client(timeout=WEB_FETCH_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for redirect_hop in range(MAX_WEB_REDIRECTS + 1):
            try:
                with client.stream("GET", current_url) as response:
                    if response.status_code in REDIRECT_STATUS_CODES:
                        if redirect_hop >= MAX_WEB_REDIRECTS:
                            raise WebFetchError("web fetch redirect limit exceeded")
                        location = response.headers.get("Location") or response.headers.get(
                            "location"
                        )
                        if not location:
                            raise WebFetchError("web fetch redirect missing location")
                        current_url = _validate_url_target(urljoin(current_url, location))
                        continue
                    if response.status_code >= 400:
                        raise WebFetchError(
                            f"web fetch failed with status {response.status_code}"
                        )
                    html = _read_response_body(response)
                    title = _extract_title(html)
                    text = _extract_text(html)
                    if not text:
                        text = title or current_url
                    return WebFetchResult(title=title, text=text, final_url=current_url)
            except httpx.TimeoutException as exc:
                raise WebFetchError("web fetch timed out") from exc
            except httpx.RequestError as exc:
                raise WebFetchError("web fetch request failed") from exc
        raise WebFetchError("web fetch redirect limit exceeded")
