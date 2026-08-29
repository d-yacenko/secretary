import ipaddress
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse

import httpx

from app.resources.constants import MAX_WEB_BODY_CHARS, MAX_WEB_FETCH_BYTES, WEB_FETCH_TIMEOUT_SECONDS


class WebFetchError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class WebFetchResult:
    title: str | None
    text: str
    final_url: str


def _host_is_blocked(hostname: str) -> bool:
    if not hostname:
        return True
    lowered = hostname.lower()
    if lowered in {"localhost", "127.0.0.1", "0.0.0.0"} or lowered.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return not ip.is_global


def _validate_public_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise WebFetchError("web url must use http or https")
    if not parsed.hostname:
        raise WebFetchError("web url hostname missing")
    if _host_is_blocked(parsed.hostname):
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


def fetch_web_page(url: str) -> WebFetchResult:
    safe_url = _validate_public_http_url(url)
    with httpx.Client(timeout=WEB_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
        with client.stream("GET", safe_url) as response:
            if response.status_code >= 400:
                raise WebFetchError(f"web fetch failed with status {response.status_code}")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_WEB_FETCH_BYTES:
                    raise WebFetchError("web fetch exceeded size limit")
                chunks.append(chunk)
            html = b"".join(chunks).decode("utf-8", errors="replace")
    final_url = str(response.url)
    title = _extract_title(html)
    text = _extract_text(html)
    if not text:
        text = title or safe_url
    return WebFetchResult(title=title, text=text, final_url=final_url)
