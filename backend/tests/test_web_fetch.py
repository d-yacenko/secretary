import pytest

from app.resources.web_fetch import WebFetchError, _validate_public_http_url


def test_web_url_blocks_localhost() -> None:
    with pytest.raises(WebFetchError, match="not allowed"):
        _validate_public_http_url("http://127.0.0.1/page")
