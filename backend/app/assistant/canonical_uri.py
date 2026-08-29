from urllib.parse import parse_qsl, urlparse, urlunparse

_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "bearer",
        "credential",
        "key",
        "password",
        "secret",
        "token",
    }
)

_LOCAL_PATH_PREFIXES = (
    "/home/",
    "/var/",
    "/tmp/",
    "/usr/",
    "/etc/",
    "/opt/",
    "/root/",
    "/private/",
    "\\\\",
)

_UNSAFE_SCHEMES = frozenset({"file", "ftp"})


def sanitize_canonical_uri_for_assistant(uri: str | None) -> str | None:
    """Return a conservative Assistant-safe canonical URI or omit it."""
    if uri is None:
        return None
    trimmed = uri.strip()
    if not trimmed:
        return None

    lowered = trimmed.lower()
    if lowered.startswith(("file:", "file://")):
        return None
    if trimmed.startswith(_LOCAL_PATH_PREFIXES):
        return None
    if len(trimmed) > 1 and trimmed[1] == ":" and trimmed[0].isalpha():
        return None

    parsed = urlparse(trimmed)
    if not parsed.scheme:
        if trimmed.startswith("/") or "\\" in trimmed:
            return None
        return None

    if parsed.scheme in _UNSAFE_SCHEMES:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.hostname
    if not host:
        return None

    netloc = host
    if parsed.port is not None:
        netloc = f"{host}:{parsed.port}"

    if parsed.query:
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in _SENSITIVE_QUERY_KEYS:
                return None

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
