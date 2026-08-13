"""Endpoint classification for provider disclosure boundaries (Sentient G3)."""

from __future__ import annotations

import pytest

from app.agent.providers.endpoints import LOOPBACK_HOSTS, classify_endpoint
from app.agent.providers.ollama import _NoRedirectHandler

LOOPBACK_URLS = [
    "http://127.0.0.1:11434",
    "http://localhost:11434",
    "http://[::1]:11434",
    "https://localhost:11434",
    "http://LOCALHOST:11434",
    "http://127.0.0.1:11434/api/chat",
]

NON_LOOPBACK_URLS = [
    "http://192.168.1.10:11434",
    "http://10.0.0.5:11434",
    "http://172.16.0.1:11434",
    "http://8.8.8.8:11434",
    "https://model-host.example",
    "http://ollama.internal:11434",
    "http://localhost.evil.com:11434",
    "http://127.0.0.1.evil.com:11434",
    "http://0.0.0.0:11434",
]

UNSAFE_URLS = [
    "ftp://127.0.0.1:11434",
    "http://user:pass@127.0.0.1:11434",
    "http://127.0.0.1:11434?model=x",
    "http://127.0.0.1:11434#fragment",
    "http://127.0.0.1:11434\n",
    "not-a-url",
    "http://",
    "",
]


@pytest.mark.parametrize("url", LOOPBACK_URLS)
def test_loopback_endpoints_classify_loopback(url: str) -> None:
    assert classify_endpoint(url) == "loopback"


@pytest.mark.parametrize("url", NON_LOOPBACK_URLS)
def test_non_loopback_endpoints_classify_external(url: str) -> None:
    assert classify_endpoint(url) == "non_loopback"


@pytest.mark.parametrize("url", UNSAFE_URLS)
def test_unsafe_endpoint_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        classify_endpoint(url)


def test_loopback_host_set_is_exact() -> None:
    assert {"127.0.0.1", "localhost", "::1"} == LOOPBACK_HOSTS


def test_no_redirect_handler_never_follows_redirects() -> None:
    handler = _NoRedirectHandler()
    assert (
        handler.redirect_request(None, None, 302, "Found", None, "http://evil.example")  # type: ignore[arg-type]
        is None
    )
    assert (
        handler.redirect_request(None, None, 307, "Temporary Redirect", None, "http://evil.example")  # type: ignore[arg-type]
        is None
    )
