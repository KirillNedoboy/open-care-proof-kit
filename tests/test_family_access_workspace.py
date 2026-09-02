from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_actor_entry_pages_are_body_only_and_non_cacheable(
    product_core_client: TestClient,
) -> None:
    product_core_client.cookies.clear()

    login = product_core_client.get("/login")
    bootstrap = product_core_client.get("/bootstrap")
    invite = product_core_client.get("/invite?code=must-not-enter-the-page")

    assert login.status_code == bootstrap.status_code == invite.status_code == 200
    assert 'id="actor-login-form"' in login.text
    assert 'id="actor-bootstrap-form"' in bootstrap.text
    assert 'id="invitation-code"' in invite.text
    assert "must-not-enter-the-page" not in invite.text
    for response in (login, bootstrap, invite):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
    assert product_core_client.get("/favicon.ico").status_code == 204


def test_register_page_is_body_only_and_uses_status_contract(
    product_core_client: TestClient,
) -> None:
    register = product_core_client.get("/register")

    assert register.status_code == 200
    assert 'id="actor-register-form"' in register.text
    assert 'id="register-password-confirm"' in register.text
    assert 'autocomplete="new-password"' in register.text
    assert "/api/family-access/v1/registration-status" in register.text
    registration_script = (ROOT / "app" / "static" / "account_registration.js").read_text(
        encoding="utf-8"
    )
    assert "register-password-confirm" not in registration_script.split("JSON.stringify", 1)[-1]
    assert register.headers["cache-control"] == "no-store"
    assert register.headers["referrer-policy"] == "no-referrer"


def test_family_access_workspace_requires_session_and_renders_management_states(
    product_core_client: TestClient,
) -> None:
    authenticated = product_core_client.get("/family-access")

    assert authenticated.status_code == 200
    assert 'id="family-access-status"' in authenticated.text
    assert 'id="access-person-selector"' in authenticated.text
    assert 'id="create-family-form"' in authenticated.text
    assert 'id="create-invitation-form"' in authenticated.text
    assert 'id="confirm-full-owner-access"' in authenticated.text
    assert "all current family access scopes" in authenticated.text.lower()
    assert "No Person selected" in authenticated.text

    product_core_client.cookies.clear()
    anonymous = product_core_client.get("/family-access", follow_redirects=False)

    assert anonymous.status_code == 307
    assert anonymous.headers["location"] == "/login?next=%2Ffamily-access"


def test_unauthenticated_live_html_pages_redirect_with_safe_next(
    product_core_client: TestClient,
) -> None:
    product_core_client.cookies.clear()

    for path in ("/workspace", "/genetics", "/chat", "/vault"):
        response = product_core_client.get(path, follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == f"/login?next=%2F{path.lstrip('/')}"

    api_response = product_core_client.get("/api/family-access/v1/me")
    assert api_response.status_code == 401
    assert api_response.json() == {"detail": "Authentication required."}


def test_login_next_rejects_external_values_and_defaults_to_workspace(
    product_core_client: TestClient,
) -> None:
    unsafe = product_core_client.get(
        "/login?next=https%3A%2F%2Fevil.example%2Fsteal"
    )
    assert 'value="/workspace"' in unsafe.text

    protocol_relative = product_core_client.get("/login?next=%2F%2Fevil.example")
    assert 'value="/workspace"' in protocol_relative.text

    safe = product_core_client.get("/login?next=%2Fgenetics")
    assert 'value="/genetics"' in safe.text


def test_family_access_browser_code_keeps_invitation_secrets_out_of_urls() -> None:
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "app" / "static" / "actor_auth.js",
            ROOT / "app" / "static" / "family_access_workspace.js",
            ROOT / "app" / "static" / "invitation.js",
        )
    )

    assert "URLSearchParams" not in scripts
    assert "location.search" not in scripts
    assert "localStorage" not in scripts
    assert "sessionStorage" not in scripts
    assert "console." not in scripts
    assert "innerHTML" not in scripts
    assert "insertAdjacentHTML" not in scripts
    assert '"/api/family-access/v1/invite/preview"' in scripts
    assert "secret: code.value" in scripts
    assert "body: JSON.stringify(payload)" in scripts
    assert "confirm_full_owner_access" in scripts
    assert "textContent" in scripts


def test_live_navigation_exposes_access_management_without_demo_crossover() -> None:
    shell = (ROOT / "app/templates/product_shell.html").read_text(encoding="utf-8")
    chat = (ROOT / "app/templates/chat.html").read_text(encoding="utf-8")
    assert 'href="/family-access"' in shell
    assert "/demo/health-vault" not in shell
    assert "/demo/health-vault" not in chat


def test_live_and_demo_chat_pages_use_separate_body_endpoints(
    product_core_client: TestClient,
) -> None:
    selected = product_core_client.put(
        "/api/family-access/v1/active-person", json={"person_id": "person-1"}
    )
    assert selected.status_code == 204

    live = product_core_client.get("/chat")
    demo = product_core_client.get("/demo/chat")
    script = (ROOT / "app" / "static" / "chat.js").read_text(encoding="utf-8")

    assert 'data-chat-endpoint="/api/chat"' in live.text
    assert 'href="/family-access"' in live.text
    assert 'data-chat-endpoint="/api/demo/chat"' in demo.text
    assert 'href="/family-access"' not in demo.text
    assert '"X-OpenCare-CSRF": csrfToken()' in script
