from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_home_has_localized_truthful_empty_states(
    product_core_client: TestClient,
) -> None:
    english = product_core_client.get("/workspace")

    assert english.status_code == 200
    assert "Welcome to your workspace" in english.text
    assert "No health profile is available yet." in english.text
    assert 'id="overview-empty"' in english.text
    assert "demo_patients" not in english.text
    assert "person-demo" not in english.text

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/workspace")

    assert russian.status_code == 200
    assert "Добро пожаловать в рабочую область" in russian.text
    assert "Профиль здоровья пока недоступен." in russian.text
    assert "Welcome to your workspace" not in russian.text


def test_workspace_reads_real_zero_state_through_authorized_paths(
    product_core_client: TestClient,
) -> None:
    people = product_core_client.get("/api/product-core/v1/people")
    assert people.status_code == 200
    assert {person["person_id"] for person in people.json()["people"]} == {
        "person-1",
        "person-2",
    }

    for path in (
        "/people/person-1/medications?include_inactive=true",
        "/people/person-1/documents",
        "/people/person-1/timeline",
    ):
        response = product_core_client.get(f"/api/product-core/v1{path}")
        assert response.status_code == 200
        payload = response.json()
        assert not any(
            values
            for key, values in payload.items()
            if key in {"medications", "documents", "events"}
        )

    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )
    assert 'metric(t("workspace.metric_records"), records.length)' in script
    assert 'metric(t("workspace.metric_documents"), state.documents.length)' in script
    assert 'metric(t("workspace.metric_medications"),' in script
    assert "demo_patients" not in script
    assert "data/demo" not in script


def test_invalid_person_selection_fails_closed_without_changing_authority(
    product_core_client: TestClient,
) -> None:
    selected = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": "person-1"},
    )
    assert selected.status_code == 204

    invalid = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": "person-not-assigned"},
    )
    assert invalid.status_code == 404

    current = product_core_client.get("/api/product-core/v1/people/person-1")
    assert current.status_code == 200
    assert current.json()["person_id"] == "person-1"

    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )
    assert 'if (!response.ok) throw Error(t("workspace.person_not_available"));' in script
    assert 'const activeId = byId("product-shell-person")?.dataset.activePersonId || "";' in script
    assert (
        "state.capabilities.document_read && state.capabilities.document_write && "
        "state.capabilities.source_write"
    ) in script
    assert "localizeWorkspaceChrome" in script
