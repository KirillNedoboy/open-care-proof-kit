from __future__ import annotations

from fastapi.testclient import TestClient

from tests.product_core_api_support import (
    create_candidate,
    create_source,
    json_headers,
)


def test_visit_brief_is_deterministic_structured_and_source_linked(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client)
    candidate_id = create_candidate(product_core_client, source_id)
    product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    payload = {
        "visit_title": "Preparation for appointment",
        "generated_at": "2026-07-26T12:00:00Z",
    }

    first = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json=payload,
        headers=json_headers(),
    )
    second = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json=payload,
        headers=json_headers(),
    )

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["source_references"] == [source_id]
    assert first.json()["records"][0]["display_name"] == "Aspirin"
    assert (
        "This brief contains user-confirmed recorded information only."
        in first.json()["markdown"]
    )
    assert "relative_path" not in first.text


def test_visit_brief_selection_and_timestamp_validation(product_core_client: TestClient) -> None:
    source_id = create_source(product_core_client)
    candidate_id = create_candidate(product_core_client, source_id)
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    record_id = confirmed.json()["id"]

    duplicate = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={
            "visit_title": "Appointment",
            "generated_at": "2026-07-26T12:00:00Z",
            "selected_record_ids": [record_id, record_id],
        },
        headers=json_headers(),
    )
    missing = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={
            "visit_title": "Appointment",
            "generated_at": "2026-07-26T12:00:00Z",
            "selected_record_ids": ["missing"],
        },
        headers=json_headers(),
    )
    naive = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={"visit_title": "Appointment", "generated_at": "2026-07-26T12:00:00"},
        headers=json_headers(),
    )

    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "request_validation_failed"
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "invalid_visit_brief_selection"
    assert naive.status_code == 422
    assert naive.json()["error"]["code"] == "request_validation_failed"


def test_empty_visit_brief_is_explicit(product_core_client: TestClient) -> None:
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={"visit_title": "Appointment", "generated_at": "2026-07-26T12:00:00Z"},
        headers=json_headers(),
    )

    assert response.status_code == 200
    assert response.json()["records"] == []
    assert "No active medication records are available." in response.json()["markdown"]


def test_visit_brief_rejects_control_text_and_oversized_record_ids(
    product_core_client: TestClient,
) -> None:
    control_text = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={
            "visit_title": "Review\nInjected heading",
            "generated_at": "2026-07-26T12:00:00Z",
        },
        headers=json_headers(),
    )
    oversized_id = product_core_client.post(
        "/api/product-core/v1/people/person-1/visit-briefs:generate",
        json={
            "visit_title": "Review",
            "generated_at": "2026-07-26T12:00:00Z",
            "selected_record_ids": ["x" * 129],
        },
        headers=json_headers(),
    )

    assert control_text.status_code == 422
    assert control_text.json()["error"]["code"] == "request_validation_failed"
    assert oversized_id.status_code == 422
    assert oversized_id.json()["error"]["code"] == "request_validation_failed"
