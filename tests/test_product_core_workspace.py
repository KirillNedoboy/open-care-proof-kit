from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_redirects_to_workspace(product_core_client: TestClient) -> None:
    response = product_core_client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/workspace"


def test_workspace_renders_a_static_product_shell(product_core_client: TestClient) -> None:
    response = product_core_client.get("/workspace")

    assert response.status_code == 200
    assert "Visit Preparation Workspace" in response.text
    assert 'id="person-selector"' in response.text
    assert 'id="create-profile-form"' in response.text
    assert 'id="edit-profile"' in response.text
    assert 'id="person-id"' not in response.text
    assert 'id="medication-form"' in response.text
    assert 'id="review-inbox"' in response.text
    assert 'id="candidate-history"' in response.text
    assert 'id="canonical-medications"' in response.text
    assert 'id="timeline"' in response.text
    assert 'id="visit-form"' in response.text
    assert 'id="visits"' in response.text
    assert 'id="visit-question-form"' in response.text
    assert 'id="visit-questions"' in response.text
    assert 'id="initialize-brief"' in response.text
    assert 'id="brief-evidence-selection"' in response.text
    assert 'id="brief-preparation-notes"' in response.text
    assert 'id="brief-revisions"' in response.text
    assert 'id="brief-markdown"' in response.text
    assert 'id="open-vault-export"' in response.text
    assert 'id="vault-export-warning"' in response.text
    assert 'id="workspace-status"' in response.text
    assert "/static/product_core_workspace.css" in response.text
    assert "/static/product_core_workspace.js" in response.text
    assert "person-demo" not in response.text


def test_chat_remains_available(product_core_client: TestClient) -> None:
    selected = product_core_client.put(
        "/api/family-access/v1/active-person", json={"person_id": "person-1"}
    )
    assert selected.status_code == 204
    response = product_core_client.get("/chat")

    assert response.status_code == 200
    assert "OpenCare chat" in response.text
