from __future__ import annotations

from fastapi.testclient import TestClient

from tests.product_core_api_support import (
    create_candidate,
    create_source,
    json_headers,
)


def test_canonical_medications_and_timeline_are_active_source_linked_and_isolated(
    product_core_client: TestClient,
) -> None:
    source_one = create_source(product_core_client, "person-1")
    source_two = create_source(product_core_client, "person-2")
    candidate_one = create_candidate(product_core_client, source_one, person_id="person-1")
    candidate_two = create_candidate(product_core_client, source_two, person_id="person-2")

    confirmed_one = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_one}/confirm",
        json={},
        headers=json_headers(),
    )
    product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_two}/confirm",
        json={},
        headers=json_headers(),
    )
    medications = product_core_client.get(
        "/api/product-core/v1/people/person-1/medications"
    )
    timeline = product_core_client.get("/api/product-core/v1/people/person-1/timeline")

    assert confirmed_one.status_code == 200
    assert len(medications.json()["medications"]) == 1
    record = medications.json()["medications"][0]
    assert record["person_id"] == "person-1"
    assert record["source_id"] == source_one
    assert record["is_active"] is True
    assert len(timeline.json()["events"]) == 1
    assert timeline.json()["events"][0]["source_id"] == source_one
    assert "relative_path" not in medications.text


def test_pending_candidates_do_not_leak_into_canonical_records(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client)
    create_candidate(product_core_client, source_id)

    response = product_core_client.get("/api/product-core/v1/people/person-1/medications")

    assert response.status_code == 200
    assert response.json() == {"medications": []}
