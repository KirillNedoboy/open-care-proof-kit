from fastapi.testclient import TestClient

from tests.product_core_api_support import json_headers


def test_people_api_creates_lists_gets_and_updates_profiles(
    product_core_client: TestClient,
) -> None:
    created = product_core_client.post(
        "/api/product-core/v1/people",
        json={"display_name": "  Ada Lovelace  ", "date_of_birth": "1815-12-10"},
        headers=json_headers(),
    )

    assert created.status_code == 201
    person = created.json()
    assert person["display_name"] == "Ada Lovelace"
    assert person["date_of_birth"] == "1815-12-10"
    assert set(person) == {
        "person_id", "display_name", "date_of_birth", "created_at", "updated_at", "is_active"
    }

    listed = product_core_client.get("/api/product-core/v1/people")
    assert listed.status_code == 200
    assert person in listed.json()["people"]
    retrieved = product_core_client.get(
        f"/api/product-core/v1/people/{person['person_id']}"
    )
    assert retrieved.json() == person

    updated = product_core_client.patch(
        f"/api/product-core/v1/people/{person['person_id']}",
        json={"display_name": "Ada", "date_of_birth": None},
        headers=json_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Ada"
    assert updated.json()["date_of_birth"] is None


def test_people_api_rejects_client_id_and_unknown_person_safely(
    product_core_client: TestClient,
) -> None:
    invalid = product_core_client.post(
        "/api/product-core/v1/people",
        json={"person_id": "client-id", "display_name": "Ada"},
        headers=json_headers(),
    )
    missing = product_core_client.get("/api/product-core/v1/people/missing")
    empty_patch = product_core_client.patch(
        "/api/product-core/v1/people/missing", json={}, headers=json_headers()
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
    assert missing.status_code == 404
    assert missing.json()["error"] == {
        "code": "person_not_found", "message": "Person was not found."
    }
    assert empty_patch.status_code == 422
    assert empty_patch.json()["error"]["code"] == "request_validation_failed"


def test_people_api_rejects_a_future_date_of_birth(product_core_client: TestClient) -> None:
    response = product_core_client.post(
        "/api/product-core/v1/people",
        json={"display_name": "Future", "date_of_birth": "2026-07-27"},
        headers=json_headers(),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
