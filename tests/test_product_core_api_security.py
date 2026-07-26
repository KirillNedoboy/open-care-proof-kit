from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from tests.product_core_api_support import json_headers


def test_product_core_rejects_cross_origin_and_incompatible_content_type(
    product_core_client: TestClient,
) -> None:
    cross_origin = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "content"},
        headers={"origin": "https://attacker.example", "content-type": "application/json"},
    )
    incompatible = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        content=b'{"person_id":"person-1","content":"content"}',
        headers={"origin": "http://testserver", "content-type": "text/plain"},
    )

    assert cross_origin.status_code == 403
    assert cross_origin.json()["error"]["code"] == "origin_rejected"
    assert incompatible.status_code == 415
    assert incompatible.json()["error"]["code"] == "json_content_type_required"


def test_existing_chat_error_contract_remains_unchanged(product_core_client: TestClient) -> None:
    response = product_core_client.post(
        "/api/chat",
        content=b'{"question":"hello"}',
        headers={"origin": "https://attacker.example", "content-type": "application/json"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request rejected."}


def test_product_core_inherits_private_password_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("OPENCARE_ENV", "production")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "false")
    monkeypatch.setenv("OPENCARE_SECRET_KEY", "s" * 32)
    monkeypatch.setenv("OPENCARE_ACCESS_PASSWORD", "password")
    clear_settings_cache()

    try:
        with TestClient(main_module.app) as client:
            response = client.get(
                "/api/product-core/v1/people/person-1/candidates",
                follow_redirects=False,
            )
            post_response = client.post(
                "/api/product-core/v1/sources/plain-text",
                json={"person_id": "person-1", "content": "content"},
                headers=json_headers(),
            )
            assert response.status_code == 307
            assert response.headers["location"].startswith("/access")
            assert post_response.status_code == 401
            assert post_response.json() == {"detail": "Private access required."}
    finally:
        clear_settings_cache()


def test_unknown_fields_use_product_core_validation_envelope(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "content", "secret": "no"},
        headers=json_headers(),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert '"no"' not in response.text
