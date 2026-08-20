from __future__ import annotations

from fastapi.testclient import TestClient

from tests.product_core_api_support import (
    create_candidate,
    create_source,
    json_headers,
)


def test_candidate_detail_listing_status_and_person_isolation(
    product_core_client: TestClient,
) -> None:
    source_one = create_source(product_core_client)
    first = create_candidate(product_core_client, source_one, display_name="Zeta")
    second = create_candidate(product_core_client, source_one, display_name="Alpha")

    listing = product_core_client.get(
        "/api/product-core/v1/people/person-1/candidates",
    )
    pending = product_core_client.get(
        "/api/product-core/v1/people/person-1/candidates?status=pending",
    )
    other = product_core_client.get(
        "/api/product-core/v1/people/person-2/candidates",
    )
    detail = product_core_client.get(f"/api/product-core/v1/candidates/{first}")

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["candidates"]] == [first, second]
    assert [item["id"] for item in pending.json()["candidates"]] == [first, second]
    assert other.json() == {"candidates": []}
    assert detail.json()["display_name"] == "Zeta"
    assert "normalized_name" not in detail.text


def test_confirmation_is_idempotent_and_review_timestamp_is_server_controlled(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client)
    candidate_id = create_candidate(product_core_client, source_id)

    first = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    second = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    candidates = product_core_client.get("/api/product-core/v1/people/person-1/candidates")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    confirmed = next(item for item in candidates.json()["candidates"] if item["id"] == candidate_id)
    assert confirmed["status"] == "confirmed"
    medications = product_core_client.get(
        "/api/product-core/v1/people/person-1/medications"
    )
    expected_locator = {
        "kind": "structured_field",
        "path": "medication",
    }
    assert first.json()["provenance_locator"] == expected_locator
    assert medications.json()["medications"][0]["provenance_locator"] == expected_locator

    assert confirmed["reviewed_at"] == "2026-07-26T12:00:00Z"

    rejected = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/reject",
        json={"reviewed_at": "2000-01-01T00:00:00Z"},
        headers=json_headers(),
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "request_validation_failed"


def test_reject_correct_and_transition_conflicts(product_core_client: TestClient) -> None:
    source_id = create_source(product_core_client)
    rejected_id = create_candidate(product_core_client, source_id)
    corrected_id = create_candidate(product_core_client, source_id, display_name="Original")

    rejected = product_core_client.post(
        f"/api/product-core/v1/candidates/{rejected_id}/reject",
        json={},
        headers=json_headers(),
    )
    replacement = product_core_client.post(
        f"/api/product-core/v1/candidates/{corrected_id}/correct",
        json={"display_name": "Corrected"},
        headers=json_headers(),
    )
    conflict = product_core_client.post(
        f"/api/product-core/v1/candidates/{rejected_id}/confirm",
        json={},
        headers=json_headers(),
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reviewed_at"] == "2026-07-26T12:00:00Z"
    assert replacement.status_code == 201
    assert replacement.json()["status"] == "pending"
    assert replacement.json()["predecessor_candidate_id"] == corrected_id
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "invalid_lifecycle_transition"


def test_candidate_validation_and_not_found_are_safe(product_core_client: TestClient) -> None:
    unknown = product_core_client.get("/api/product-core/v1/candidates/missing")
    invalid = product_core_client.post(
        "/api/product-core/v1/candidates/medications",
        json={"person_id": "", "source_id": "source", "display_name": "X"},
        headers=json_headers(),
    )

    assert unknown.status_code == 404
    assert unknown.json() == {
        "error": {"code": "candidate_not_found", "message": "Candidate was not found."}
    }
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
