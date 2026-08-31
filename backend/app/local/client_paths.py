"""Client-reported source path helpers."""

import hashlib


def normalize_client_source_path(source_path: str) -> str:
    text = source_path.replace("\\", "/").strip()
    while "//" in text:
        text = text.replace("//", "/")
    return text


def build_client_source_external_id(device_key: str, source_path: str) -> str:
    normalized = normalize_client_source_path(source_path)
    return f"{device_key}:client-source:{normalized}"


def cheap_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
