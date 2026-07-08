from __future__ import annotations

import argparse
import http.client
import ssl
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class CheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResult:
    status: int
    location: str | None
    body: bytes = b""
    headers: tuple[tuple[str, str], ...] = ()


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CheckError("Base URL must be an absolute http or https URL.")
    return normalized


def _is_expected_redirect(location: str | None, *, path: str, next_path: str | None) -> bool:
    if location is None:
        return False
    parsed = urlsplit(location)
    if parsed.path != path:
        return False
    if next_path is None:
        return True
    return parse_qs(parsed.query).get("next") == [next_path]


def validate_vault_without_password(result: HttpResult) -> str:
    if result.status == 200:
        return "public"
    if result.status in REDIRECT_STATUS_CODES and _is_expected_redirect(
        result.location,
        path="/access",
        next_path="/vault",
    ):
        return "private_redirect"
    raise CheckError(f"Unexpected /vault response without password: {result.status}.")


def validate_private_vault_flow(
    *,
    initial: HttpResult,
    login: HttpResult,
    unlocked: HttpResult,
) -> None:
    if not (
        initial.status in REDIRECT_STATUS_CODES
        and _is_expected_redirect(initial.location, path="/access", next_path="/vault")
    ):
        raise CheckError("Expected /vault to redirect to /access before login.")
    if not (
        login.status in REDIRECT_STATUS_CODES
        and _is_expected_redirect(login.location, path="/vault", next_path=None)
    ):
        raise CheckError("Expected successful login redirect to /vault.")
    if unlocked.status != 200:
        raise CheckError("Expected unlocked /vault to return 200.")


def _build_connection(target_url: str, *, timeout: float) -> http.client.HTTPConnection:
    parsed = urlsplit(target_url)
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    return http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)


def _request(
    base_url: str,
    path: str,
    *,
    timeout: float,
    method: str = "GET",
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
) -> HttpResult:
    target_url = urljoin(f"{base_url}/", path.lstrip("/"))
    parsed = urlsplit(target_url)
    request_headers = {"User-Agent": "opencare-smoke-check/1.0"}
    if headers is not None:
        request_headers.update(headers)
    connection = _build_connection(target_url, timeout=timeout)
    try:
        request_path = parsed.path or "/"
        if parsed.query:
            request_path = f"{request_path}?{parsed.query}"
        connection.request(method, request_path, body=body, headers=request_headers)
        response = connection.getresponse()
        response_body = response.read()
        response_headers = tuple(response.getheaders())
        return HttpResult(
            status=response.status,
            location=response.getheader("Location"),
            body=response_body,
            headers=response_headers,
        )
    finally:
        connection.close()


def _extract_cookie(result: HttpResult) -> str:
    for key, value in result.headers:
        if key.lower() == "set-cookie":
            return value.split(";", 1)[0]
    raise CheckError("Expected login response to set an access cookie.")


def run_smoke_check(*, base_url: str, password: str | None, timeout: float) -> list[str]:
    normalized_base_url = normalize_base_url(base_url)
    notes: list[str] = []

    healthz = _request(normalized_base_url, "/healthz", timeout=timeout)
    if healthz.status != 200:
        raise CheckError(f"/healthz returned {healthz.status}, expected 200.")
    notes.append("healthz_ok")

    readyz = _request(normalized_base_url, "/readyz", timeout=timeout)
    if readyz.status != 200:
        raise CheckError(f"/readyz returned {readyz.status}, expected 200.")
    notes.append("readyz_ok")

    initial_vault = _request(normalized_base_url, "/vault", timeout=timeout)
    vault_mode = validate_vault_without_password(initial_vault)
    notes.append(f"vault_mode={vault_mode}")

    if vault_mode == "public":
        return notes

    if password is None:
        notes.append("private_gate_detected")
        return notes

    access_page = _request(normalized_base_url, "/access?next=%2Fvault", timeout=timeout)
    if access_page.status != 200:
        raise CheckError(f"/access returned {access_page.status}, expected 200.")

    login_body = urlencode({"password": password, "next": "/vault"}).encode("utf-8")
    login_result = _request(
        normalized_base_url,
        "/access",
        timeout=timeout,
        method="POST",
        body=login_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    cookie = _extract_cookie(login_result)
    unlocked_vault = _request(
        normalized_base_url,
        "/vault",
        timeout=timeout,
        headers={"Cookie": cookie},
    )
    validate_private_vault_flow(
        initial=initial_vault,
        login=login_result,
        unlocked=unlocked_vault,
    )
    notes.append("private_login_ok")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-check OpenCare self-hosted deployment health endpoints and /vault access."
        )
    )
    parser.add_argument("--base-url", required=True, help="Base URL such as https://host")
    parser.add_argument(
        "--password",
        help="Optional private access password for verifying the /access -> /vault flow.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds. Default: 5.0",
    )
    args = parser.parse_args(argv)

    try:
        notes = run_smoke_check(
            base_url=args.base_url,
            password=args.password,
            timeout=args.timeout,
        )
    except CheckError as exc:
        print(f"smoke_check: FAIL: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"smoke_check: FAIL: {exc}", file=sys.stderr)
        return 1

    for note in notes:
        print(f"smoke_check: OK: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
