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
    assert "full control" in authenticated.text.lower()
    assert "No Person selected" in authenticated.text

    product_core_client.cookies.clear()
    anonymous = product_core_client.get("/family-access", follow_redirects=False)

    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "authentication_required"


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
    for template_name in (
        "product_core_workspace.html",
        "product_core_vault.html",
        "chat.html",
    ):
        template = (ROOT / "app" / "templates" / template_name).read_text(
            encoding="utf-8"
        )
        assert 'href="/family-access"' in template
        assert "/demo/health-vault" not in template


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
    assert 'headers["X-OpenCare-CSRF"] = csrfToken()' in script
