from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.ui_localization import TRANSLATIONS

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


def test_workspace_sections_are_localized_in_both_catalogs(
    product_core_client: TestClient,
) -> None:
    english = product_core_client.get("/workspace")
    assert english.status_code == 200
    for label in (
        "Review",
        "Documents",
        "Records",
        "Timeline",
        "Visit Brief",
        "Fact type",
        "Status",
        "Add for review",
    ):
        assert label in english.text

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/workspace")
    assert russian.status_code == 200
    for label in (
        "Проверка",
        "Документы",
        "Записи",
        "Активность",
        "Краткая информация о визите",
        "Тип факта",
        "Статус",
        "Добавить на проверку",
    ):
        assert label in russian.text
    for label in ("Review", "Documents", "Records", "Timeline", "Fact type"):
        assert label not in russian.text


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


def test_workspace_catalog_has_matching_en_ru_workspace_keys() -> None:
    english = {key for key in TRANSLATIONS["en"] if key.startswith("workspace.")}
    russian = {key for key in TRANSLATIONS["ru"] if key.startswith("workspace.")}
    assert english <= russian


def test_workspace_preserves_machine_values_and_navigation_contracts() -> None:
    template = (ROOT / "app" / "templates" / "product_core_workspace.html").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )
    for anchor in ("records", "documents", "timeline"):
        assert f'href="#{anchor}"' in template
    for value in ('"pending"', '"confirmed"', '"corrected"', '"rejected"', '"unsupported"'):
        assert value in template or value in script
    assert all(route not in template for route in ("/health", "/documents", "/activity"))
    assert "state.loadVersion" in script
    assert "shouldApplyResponse" in script


def test_workspace_rerender_clears_person_scoped_review_and_timeline_cards() -> None:
    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )
    render_start = script.index('function render()')
    render_body = script[render_start : script.index('function renderOverview()', render_start)]
    assert 'clear(inbox); clear(timeline);' in render_body
    assert "if (!EVENT_LABELS[item.event_type]) return item.title;" in script
    assert "eventTitle(item)" in script
