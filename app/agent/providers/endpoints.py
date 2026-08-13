"""Provider endpoint classification (Sentient G3).

Classification is determined by the resolved endpoint, not by who owns it.
Loopback endpoints (``127.0.0.1``, ``localhost``, ``::1``) stay inside the
local-only disclosure boundary; anything else is an external disclosure and
requires the full G2 external-consent flow. DNS is never resolved and names
that merely look local are not trusted.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.config import _is_valid_responses_url

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def classify_endpoint(url: str) -> str:
    """Return ``"loopback"`` or ``"non_loopback"`` for a safe HTTP(S) URL.

    Raises ``ValueError`` for unsafe/invalid URLs: embedded credentials,
    query string, fragment, non-http scheme, control characters, missing
    hostname, or unparseable port.
    """
    if not _is_valid_responses_url(url):
        raise ValueError("Invalid provider endpoint URL.")
    parsed = urlsplit(url)
    hostname = parsed.hostname
    assert hostname is not None
    normalized = hostname.strip("[]").lower()
    return "loopback" if normalized in LOOPBACK_HOSTS else "non_loopback"
