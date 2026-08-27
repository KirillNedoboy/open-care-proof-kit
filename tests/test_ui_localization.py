from collections.abc import Mapping

import pytest
from starlette.requests import Request

from app.ui_localization import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    TRANSLATIONS,
    get_translations,
    resolve_locale,
    translate,
)


def _request(
    locale_cookie: str | None = None,
    *,
    query_string: bytes = b"",
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    headers = list(extra_headers or [])
    if locale_cookie is not None:
        headers.append((b"cookie", f"opencare_locale={locale_cookie}".encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/workspace",
            "query_string": query_string,
            "headers": headers,
        }
    )


def test_supported_locales_and_default_are_stable() -> None:
    assert SUPPORTED_LOCALES == ("en", "ru")
    assert DEFAULT_LOCALE == "en"
    assert set(TRANSLATIONS) == set(SUPPORTED_LOCALES)
    assert all(isinstance(catalog, Mapping) for catalog in TRANSLATIONS.values())
    assert set(TRANSLATIONS["ru"]) == set(TRANSLATIONS["en"])


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_resolve_locale_accepts_exact_supported_cookie(locale: str) -> None:
    request = _request(locale)

    assert resolve_locale(request) == locale
    assert request.cookies["opencare_locale"] == locale


@pytest.mark.parametrize(
    "cookie_value",
    [None, "", "EN", "Ru", "ru-RU", "%20ru", "ru%20", "en-US", "../../ru"],
)
def test_resolve_locale_rejects_missing_or_non_exact_cookie(cookie_value: str | None) -> None:
    assert resolve_locale(_request(cookie_value)) == DEFAULT_LOCALE


def test_resolve_locale_reads_only_locale_cookie_and_is_side_effect_free() -> None:
    request = _request(
        None,
        query_string=b"locale=ru",
        extra_headers=[(b"accept-language", b"ru"), (b"x-locale", b"ru")],
    )
    cookies_before = dict(request.cookies)

    assert resolve_locale(request) == DEFAULT_LOCALE
    assert dict(request.cookies) == cookies_before
    assert resolve_locale(_request("ru")) == "ru"
    assert resolve_locale(_request("ru")) == "ru"


def test_get_translations_uses_english_for_invalid_locale_and_returns_a_copy() -> None:
    english = get_translations("en")
    invalid = get_translations("de")

    assert invalid == english
    invalid["nav.workspace"] = "changed"
    assert get_translations("en")["nav.workspace"] == "Workspace"


def test_translate_uses_requested_catalog_then_safe_english_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert translate("ru", "nav.workspace") == "Рабочая область"
    assert translate("not-supported", "nav.workspace") == "Workspace"

    monkeypatch.delitem(TRANSLATIONS["ru"], "nav.workspace")
    assert translate("ru", "nav.workspace") == "Workspace"
    assert translate("ru", "unknown.shared.label") == "unknown.shared.label"


@pytest.mark.parametrize(
    "machine_identifier",
    ["confirmed", "consent_required", "visit_read", "CYP2C19", "rs4244285"],
)
def test_unknown_machine_identifiers_are_not_mutated(machine_identifier: str) -> None:
    assert translate("ru", machine_identifier) == machine_identifier
    assert translate("en", machine_identifier) == machine_identifier
