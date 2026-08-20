from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_redirects_to_workspace(product_core_client: TestClient) -> None:
    response = product_core_client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/workspace"


def test_workspace_renders_complete_p2_health_workspace(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/workspace")

    assert response.status_code == 200
    assert "OpenCare Health Workspace" in response.text
    assert "Visit Preparation Workspace" not in response.text
    for section_id in (
        "person-context",
        "overview",
        "review",
        "records",
        "timeline",
        "visits-brief",
        "export",
    ):
        assert f'href="#{section_id}"' in response.text
        assert f'id="{section_id}"' in response.text
    for element_id in (
        "person-selector",
        "selected-person",
        "create-profile-form",
        "edit-profile",
        "medication-form",
        "review-inbox",
        "review-search",
        "records-medication",
        "records-condition",
        "records-lab",
        "timeline-list",
        "visit-form",
        "visits",
        "visit-question-form",
        "visit-questions",
        "initialize-brief",
        "brief-evidence-selection",
        "brief-preparation-notes",
        "brief-revisions",
        "brief-markdown",
        "open-vault-export",
        "vault-export-warning",
        "workspace-status",
    ):
        assert f'id="{element_id}"' in response.text
    assert "Select confirmed evidence" in response.text
    assert "full owner access" in response.text
    assert 'id="person-id"' not in response.text
    assert "person-demo" not in response.text
    assert "/static/workspace_state.js" in response.text
    assert "/static/product_core_workspace.css" in response.text
    assert "/static/product_core_workspace.js" in response.text


def test_chat_remains_available(product_core_client: TestClient) -> None:
    selected = product_core_client.put(
        "/api/family-access/v1/active-person", json={"person_id": "person-1"}
    )
    assert selected.status_code == 204
    response = product_core_client.get("/chat")

    assert response.status_code == 200
    assert "OpenCare chat" in response.text
