from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request


def is_same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        return True
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    request_host = request.url.hostname
    if parsed.hostname != request_host:
        return False
    try:
        origin_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        request_port = request.url.port or (443 if request.url.scheme == "https" else 80)
    except ValueError:
        return False
    return origin_port == request_port and parsed.scheme == request.url.scheme
