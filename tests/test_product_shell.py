from __future__ import annotations

from fastapi.testclient import TestClient


def test_workspace_uses_localized_shared_shell_in_english_and_russian(
    product_core_client: TestClient,
) -> None:
    english = product_core_client.get("/workspace")
    assert english.status_code == 200
    assert '<html lang="en">' in english.text
    assert 'class="product-shell__sidebar"' in english.text
    assert 'aria-current="page"' in english.text
    assert "Overview" in english.text
    assert 'id="product-shell-locale"' in english.text
    assert 'value="ru"' in english.text

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/workspace")
    assert russian.status_code == 200
    assert '<html lang="ru">' in russian.text
    assert "Обзор" in russian.text
    assert "Язык" in russian.text
    assert "Пользователь не выбран" in russian.text
    assert 'id="product-shell-person"' in russian.text

def test_genetics_uses_application_shell_and_preserves_local_navigation(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/genetics")
    assert response.status_code == 200
    assert 'href="/genetics" aria-current="page"' in response.text
    assert 'class="workspace-tabs"' in response.text
    assert 'id="tab-overview"' in response.text
    assert 'id="panel-research"' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_shared_shell_person_slot_truthfully_represents_empty_and_selected_state(
    product_core_client: TestClient,
) -> None:
    empty = product_core_client.get("/workspace")
    assert empty.status_code == 200
    assert "No person selected" in empty.text
    assert 'data-active-person-id=""' in empty.text

    csrf = product_core_client.cookies.get("opencare_csrf")
    assert csrf is not None
    selected = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": "person-1"},
        headers={"origin": "http://testserver", "x-opencare-csrf": csrf},
    )
    assert selected.status_code == 204
    rendered = product_core_client.get("/workspace")
    assert rendered.status_code == 200
    assert "Selected person" in rendered.text
    assert 'data-active-person-id="person-1"' in rendered.text


def test_invalid_locale_cannot_change_auth_or_inject_markup(
    product_core_client: TestClient,
) -> None:
    product_core_client.cookies.set("opencare_locale", "ru\"><script>alert(1)</script>", path="/")
    rendered = product_core_client.get("/workspace")
    assert rendered.status_code == 200
    assert '<html lang="en">' in rendered.text
    assert "<script>alert(1)</script>" not in rendered.text

    product_core_client.cookies.clear()
    protected = product_core_client.get("/workspace", follow_redirects=False)
    assert protected.status_code == 307
    assert protected.headers["location"] == "/login?next=%2Fworkspace"


def test_shared_shell_does_not_create_new_backend_routes(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/settings", follow_redirects=False)
    assert response.status_code == 404
    assert product_core_client.get("/family-access#account-settings").status_code == 200


def test_authenticated_chat_renders_shared_shell_and_localized_content(
    product_core_client: TestClient,
) -> None:
    selected = product_core_client.put(
        "/api/family-access/v1/active-person", json={"person_id": "person-1"}
    )
    assert selected.status_code == 204
    english = product_core_client.get("/chat")
    assert english.status_code == 200
    assert '<html lang="en">' in english.text
    assert 'class="product-shell__sidebar"' in english.text
    assert 'href="/chat" aria-current="page"' in english.text
    assert 'class="chat-content"' in english.text
    assert 'class="chat-sidebar"' not in english.text
    assert "Ask about your recorded vault" in english.text

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/chat")
    assert russian.status_code == 200
    assert '<html lang="ru">' in russian.text
    assert "Спросите о записанных данных" in russian.text
    assert "Отправить" in russian.text


def test_demo_chat_keeps_demo_endpoint_without_authenticated_shell(
    product_core_client: TestClient,
) -> None:
    demo = product_core_client.get("/demo/chat")
    assert demo.status_code == 200
    assert 'data-chat-endpoint="/api/demo/chat"' in demo.text
    assert 'class="product-shell__sidebar"' not in demo.text
