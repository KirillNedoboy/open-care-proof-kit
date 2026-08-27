from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache


@pytest.fixture
def uninitialized_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    monkeypatch.setenv("OPENCARE_PUBLIC_REGISTRATION", "true")
    clear_settings_cache()
    try:
        with TestClient(main_module.app) as client:
            yield client
    finally:
        clear_settings_cache()

@pytest.mark.parametrize(
    ("locale", "lang", "login_title", "register_title", "invite_title"),
    [
        ("en", "en", "Welcome back", "Create your account", "Use an invitation"),
        ("ru", "ru", "С возвращением", "Создайте аккаунт", "Использовать приглашение"),
    ],
)
def test_public_auth_pages_render_localized_shell_and_copy(
    product_core_client: TestClient,
    locale: str,
    lang: str,
    login_title: str,
    register_title: str,
    invite_title: str,
) -> None:
    product_core_client.cookies.set("opencare_locale", locale, path="/")

    login = product_core_client.get("/login")
    register = product_core_client.get("/register")
    bootstrap = product_core_client.get("/bootstrap")
    invitation = product_core_client.get("/invite")

    for response in (login, register, bootstrap, invitation):
        assert response.status_code == 200
        assert f'<html lang="{lang}">' in response.text
        assert 'class="public-auth-shell' in response.text
        assert 'id="public-auth-locale"' in response.text
        assert "/static/product_shell.css" in response.text
        assert "/static/public_auth.css" in response.text
        assert "opencare_locale" not in response.text

    assert login_title in login.text
    assert register_title in register.text
    assert invite_title in invitation.text
    if locale == "ru":
        assert "Приглашение" in invitation.text
    else:
        assert "invitation" in invitation.text.lower()


def test_login_exposes_invitation_as_secondary_and_keeps_safe_next(
    product_core_client: TestClient,
) -> None:
    login = product_core_client.get("/login?next=%2Fgenetics")
    assert login.status_code == 200
    assert 'id="login-next"' in login.text
    assert 'value="/genetics"' in login.text
    assert 'href="/invite"' in login.text
    assert 'href="/register"' in login.text
    assert 'id="registration-link"' in login.text
    assert 'id="bootstrap-link"' in login.text

    unsafe = product_core_client.get("/login?next=https%3A%2F%2Fevil.example%2Fsteal")
    assert 'value="/workspace"' in unsafe.text

def test_registration_prebootstrap_state_is_unavailable_without_usable_form(
    uninitialized_client: TestClient,
) -> None:
    status = uninitialized_client.get("/api/family-access/v1/registration-status")
    assert status.json() == {
        "registration_enabled": True,
        "registration_available": False,
    }
    page = uninitialized_client.get("/register")
    assert page.status_code == 200
    assert '<form id="actor-register-form" class="auth-form" hidden>' in page.text
    assert "This installation must be set up by its operator" in page.text


def test_production_bootstrap_secret_field_is_present_but_secret_is_not_rendered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "production")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    monkeypatch.setenv("OPENCARE_PUBLIC_REGISTRATION", "false")
    monkeypatch.setenv("OPENCARE_SECRET_KEY", "s" * 32)
    monkeypatch.setenv("OPENCARE_BOOTSTRAP_SECRET", "b" * 32)
    clear_settings_cache()
    try:
        with TestClient(main_module.app) as client:
            page = client.get("/bootstrap")
    finally:
        clear_settings_cache()

    assert page.status_code == 200
    assert 'id="bootstrap-secret"' in page.text
    assert "b" * 32 not in page.text


def test_registration_disabled_is_not_rendered_as_usable_form(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/register")
    assert response.status_code == 200
    assert '<form id="actor-register-form" class="auth-form" hidden>' in response.text
    assert 'id="registration-disabled"' in response.text
    assert "invitation" in response.text.lower()
    form = response.text.split('<form id="actor-register-form"', 1)[1].split("</form>", 1)[0]
    for forbidden in ("person_ids", "own_person_id", "installation_admin", "scope"):
        assert forbidden not in form.lower()

def test_bootstrap_initialized_state_hides_form_and_preserves_advanced_controls(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/bootstrap")
    assert response.status_code == 200
    assert '<form id="actor-bootstrap-form" class="auth-form" hidden>' in response.text
    assert 'id="bootstrap-setup-complete"' in response.text
    assert 'href="/login"' in response.text
    assert '<details>' in response.text
    assert 'id="bootstrap-person-ids"' in response.text
    assert 'id="bootstrap-secret"' not in response.text
    assert "b" * 32 not in response.text

def test_invitation_page_keeps_code_out_of_url_and_explains_family_sharing(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/invite?code=must-not-render")
    assert response.status_code == 200
    assert "must-not-render" not in response.text
    assert 'id="invitation-code"' in response.text
    assert 'autocomplete="off"' in response.text
    assert "not required for normal sign-in" in response.text
    assert 'id="invitation-register-form"' in response.text
    assert 'id="invitation-accept-form"' in response.text


def test_locale_cannot_bypass_protected_route_or_inject_html(
    product_core_client: TestClient,
) -> None:
    product_core_client.cookies.set("opencare_locale", 'ru\"><script>alert(1)</script>', path="/")
    login = product_core_client.get("/login")
    assert login.status_code == 200
    assert '<html lang="en">' in login.text
    assert "<script>alert(1)</script>" not in login.text

    product_core_client.cookies.clear()
    protected = product_core_client.get("/workspace", follow_redirects=False)
    assert protected.status_code == 307
    assert protected.headers["location"] == "/login?next=%2Fworkspace"
