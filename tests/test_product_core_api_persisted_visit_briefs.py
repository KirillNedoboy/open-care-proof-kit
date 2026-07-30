from fastapi.testclient import TestClient

from tests.product_core_api_support import (
    create_candidate,
    create_source,
    json_headers,
)


def _visit(client: TestClient) -> str:
    response = client.post(
        "/api/product-core/v1/visits",
        json={"person_id": "person-1", "title": "Medication review"},
        headers=json_headers(),
    )
    assert response.status_code == 201
    return response.json()["visit_id"]


def _confirmed_record(client: TestClient) -> str:
    candidate_id = create_candidate(client, create_source(client))
    response = client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_persisted_visit_brief_lifecycle_and_export(product_core_client: TestClient) -> None:
    visit_id = _visit(product_core_client)
    record_id = _confirmed_record(product_core_client)
    initialized = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief",
        json={},
        headers=json_headers(),
    )
    assert initialized.status_code == 201

    missing_expected = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={"selected_record_ids": [record_id]},
        headers=json_headers(),
    )
    assert missing_expected.status_code == 422
    generated = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={
            "selected_record_ids": [record_id],
            "expected_current_revision_number": None,
        },
        headers=json_headers(),
    )
    assert generated.status_code == 201
    assert generated.json()["revision_number"] == 1
    assert "content_hash" not in generated.json()

    conflict = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:user-edit",
        json={"preparation_notes": "Bring records", "expected_current_revision_number": 9},
        headers=json_headers(),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "visit_brief_conflict"
    edited = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:user-edit",
        json={"preparation_notes": "Bring records", "expected_current_revision_number": 1},
        headers=json_headers(),
    )
    assert edited.status_code == 201
    assert edited.json()["revision_number"] == 2

    exported = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/current:export",
        json={},
        headers=json_headers(),
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "text/markdown; charset=utf-8"
    assert exported.headers["content-disposition"] == (
        'attachment; filename="opencare-visit-brief-r2.md"'
    )
    assert "Bring records" in exported.text


def test_persisted_visit_brief_rejects_foreign_evidence(product_core_client: TestClient) -> None:
    visit_id = _visit(product_core_client)
    foreign_source = create_source(product_core_client, "person-2")
    foreign_candidate = create_candidate(product_core_client, foreign_source, person_id="person-2")
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{foreign_candidate}/confirm",
        json={},
        headers=json_headers(),
    )
    product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief",
        json={},
        headers=json_headers(),
    )
    invalid = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={
            "selected_record_ids": [confirmed.json()["id"]],
            "expected_current_revision_number": None,
        },
        headers=json_headers(),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
