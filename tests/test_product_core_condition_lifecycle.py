from __future__ import annotations

from fastapi.testclient import TestClient

from tests.product_core_api_support import json_headers

CONDITION_CANDIDATE_PATH = "/api/product-core/v1/candidates/conditions"
CONDITION_SOURCE_PATH = "/api/product-core/v1/sources/manual-condition"
CONDITIONS_PATH = "/api/product-core/v1/people/person-1/conditions"


def create_condition_source(
    client: TestClient, person_id: str = "person-1", display_name: str = "Asthma"
) -> str:
    response = client.post(
        CONDITION_SOURCE_PATH,
        json={"person_id": person_id, "condition": {"display_name": display_name}},
        headers=json_headers(),
    )
    assert response.status_code == 201, response.text
    return response.json()["source"]["source_id"]


def create_condition_candidate(
    client: TestClient,
    source_id: str,
    *,
    person_id: str = "person-1",
    display_name: str = "Asthma",
    status_text: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "person_id": person_id,
        "source_id": source_id,
        "display_name": display_name,
    }
    if status_text is not None:
        payload["status_text"] = status_text
    response = client.post(
        CONDITION_CANDIDATE_PATH,
        json=payload,
        headers=json_headers(),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_condition_lifecycle_confirms_into_canonical_with_timeline_and_provenance(
    product_core_client: TestClient,
) -> None:
    source_id = create_condition_source(product_core_client)
    candidate_id = create_condition_candidate(
        product_core_client, source_id, display_name="Asthma", status_text="chronic"
    )

    candidates = product_core_client.get(
        "/api/product-core/v1/people/person-1/condition-candidates"
    )
    detail = product_core_client.get(
        f"/api/product-core/v1/candidates/conditions/{candidate_id}"
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    records = product_core_client.get(CONDITIONS_PATH)
    timeline = product_core_client.get("/api/product-core/v1/people/person-1/timeline")
    record_detail = product_core_client.get(
        f"/api/product-core/v1/conditions/{confirmed.json()['id']}"
    )

    assert [item["id"] for item in candidates.json()["candidates"]] == [candidate_id]
    assert detail.json()["fact_type"] == "condition"
    assert detail.json()["display_name"] == "Asthma"
    assert detail.json()["status_text"] == "chronic"
    assert detail.json()["provenance_locator"] == {
        "kind": "structured_field",
        "path": "data.condition.display_name",
    }
    assert confirmed.status_code == 200
    assert confirmed.json()["is_active"] is True
    assert records.json()["conditions"][0]["display_name"] == "Asthma"
    assert records.json()["conditions"][0]["status_text"] == "chronic"
    assert records.json()["conditions"][0]["source_id"] == source_id
    assert timeline.json()["events"][0]["event_type"] == "condition_confirmed"
    assert timeline.json()["events"][0]["fact_type"] == "condition"
    assert timeline.json()["events"][0]["title"] == "Condition confirmed: Asthma"
    assert record_detail.json()["candidate_id"] == candidate_id
    assert record_detail.json()["is_active"] is True


def test_condition_reject_and_unsupported_create_no_canonical(
    product_core_client: TestClient,
) -> None:
    source_id = create_condition_source(product_core_client, display_name="Eczema")
    rejected_id = create_condition_candidate(
        product_core_client, source_id, display_name="Eczema"
    )
    unsupported_id = create_condition_candidate(
        product_core_client, source_id, display_name="Eczema"
    )

    rejected = product_core_client.post(
        f"/api/product-core/v1/candidates/{rejected_id}/reject",
        json={},
        headers=json_headers(),
    )
    unsupported = product_core_client.post(
        f"/api/product-core/v1/candidates/{unsupported_id}/unsupported",
        json={},
        headers=json_headers(),
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert unsupported.status_code == 200
    assert unsupported.json()["status"] == "unsupported"
    records = product_core_client.get(CONDITIONS_PATH)
    assert records.json() == {"conditions": []}


def test_condition_duplicate_confirm_creates_single_canonical(
    product_core_client: TestClient,
) -> None:
    source_id = create_condition_source(product_core_client)
    candidate_id = create_condition_candidate(product_core_client, source_id)

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
    records = product_core_client.get(CONDITIONS_PATH)
    timeline = product_core_client.get("/api/product-core/v1/people/person-1/timeline")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(records.json()["conditions"]) == 1
    assert len(timeline.json()["events"]) == 1


def test_condition_correction_preserves_lineage_and_supersedes_canonical(
    product_core_client: TestClient,
) -> None:
    source_id = create_condition_source(product_core_client, display_name="Asthma")
    candidate_id = create_condition_candidate(
        product_core_client, source_id, display_name="Asthma"
    )

    # Path A: correcting a PENDING candidate marks it corrected and creates a
    # pending successor (no canonical involved). The corrected value must be
    # supported by a source, so the correction references a replacement source.
    variant_source = create_condition_source(
        product_core_client, display_name="Asthma variant"
    )
    pending_replacement = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/correct:condition",
        json={"display_name": "Asthma variant", "source_id": variant_source},
        headers=json_headers(),
    )
    assert pending_replacement.status_code == 201
    assert pending_replacement.json()["status"] == "pending"
    assert pending_replacement.json()["predecessor_candidate_id"] == candidate_id
    original_after = product_core_client.get(
        f"/api/product-core/v1/candidates/conditions/{candidate_id}"
    )
    assert original_after.json()["status"] == "corrected"
    assert product_core_client.get(CONDITIONS_PATH).json() == {"conditions": []}

    # Path B: correcting a CONFIRMED (active) candidate creates a successor
    # that keeps the original confirmed; confirming the successor supersedes
    # the old canonical and writes a deterministic corrected event.
    second_source = create_condition_source(
        product_core_client, display_name="Asthma (seasonal)"
    )
    second_candidate = create_condition_candidate(
        product_core_client, second_source, display_name="Asthma (seasonal)"
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{second_candidate}/confirm",
        json={},
        headers=json_headers(),
    )
    replacement = product_core_client.post(
        f"/api/product-core/v1/candidates/{second_candidate}/correct:condition",
        json={
            "display_name": "Asthma (seasonal)",
            "source_id": second_source,
        },
        headers=json_headers(),
    )
    corrected = product_core_client.post(
        f"/api/product-core/v1/candidates/{replacement.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    old_record_id = confirmed.json()["id"]
    new_record_id = corrected.json()["id"]

    records = product_core_client.get(
        CONDITIONS_PATH + "?include_inactive=true"
    ).json()["conditions"]
    by_id = {record["id"]: record for record in records}
    assert by_id[old_record_id]["is_active"] is False
    assert by_id[old_record_id]["superseded_by_record_id"] == new_record_id
    assert by_id[new_record_id]["is_active"] is True
    assert by_id[new_record_id]["display_name"] == "Asthma (seasonal)"

    timeline = product_core_client.get(
        "/api/product-core/v1/people/person-1/timeline"
    ).json()["events"]
    event_types = {(event["event_type"], event["canonical_record_id"]) for event in timeline}
    assert ("condition_confirmed", new_record_id) in event_types
    assert ("condition_corrected", old_record_id) in event_types

    original = product_core_client.get(
        f"/api/product-core/v1/candidates/conditions/{second_candidate}"
    )
    assert original.json()["status"] == "confirmed"


def test_condition_person_isolation_and_hidden_ids(
    product_core_client: TestClient,
) -> None:
    source_id = create_condition_source(product_core_client, person_id="person-1")
    candidate_id = create_condition_candidate(product_core_client, source_id)
    record_id = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    ).json()["id"]

    other = product_core_client.get("/api/product-core/v1/people/person-2/conditions")
    visible = product_core_client.get(f"/api/product-core/v1/conditions/{record_id}")
    missing = product_core_client.get("/api/product-core/v1/conditions/missing-record")
    hidden_candidate = product_core_client.get(
        f"/api/product-core/v1/candidates/conditions/{candidate_id}"
    )
    missing_candidate = product_core_client.get(
        "/api/product-core/v1/candidates/conditions/missing-candidate"
    )

    assert other.json() == {"conditions": []}
    assert visible.status_code == 200
    assert missing.status_code == 404
    # The owner may read the candidate; a nonexistent candidate is 404. The
    # hidden-404 privacy shape for unauthorized actors is covered by the
    # access-enforcement suite (Wrong Person scenario).
    assert hidden_candidate.status_code == 200
    assert missing_candidate.status_code == 404


def test_plain_text_condition_candidate_requires_valid_span_locator(
    product_core_client: TestClient,
) -> None:
    source = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "Reports seasonal asthma."},
        headers=json_headers(),
    ).json()["source"]
    source_id = source["source_id"]

    without_locator = product_core_client.post(
        CONDITION_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source_id,
            "display_name": "Asthma",
        },
        headers=json_headers(),
    )
    assert without_locator.status_code == 422
    assert without_locator.json()["error"]["code"] == "provenance_validation_failed"

    wrong_span = product_core_client.post(
        CONDITION_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source_id,
            "display_name": "Asthma",
            "provenance_locator": {"kind": "span", "start": 100, "end": 105},
        },
        headers=json_headers(),
    )
    assert wrong_span.status_code == 422

    valid = product_core_client.post(
        CONDITION_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source_id,
            "display_name": "asthma",
            "provenance_locator": {"kind": "span", "start": 17, "end": 23},
        },
        headers=json_headers(),
    )
    assert valid.status_code == 201
    assert valid.json()["provenance_locator"] == {
        "kind": "span",
        "start": 17,
        "end": 23,
    }


def test_condition_foreign_source_is_hidden_at_the_api_boundary(
    product_core_client: TestClient,
) -> None:
    """A source belonging to another Person is indistinguishable from a
    missing source at the API boundary (404), so a client can never confirm
    source ownership or exfiltrate existence. The service-level
    PersonMismatchError (409) path is exercised directly in the lifecycle
    tests when the source is reachable."""
    source_id = create_condition_source(product_core_client, person_id="person-2")

    response = product_core_client.post(
        CONDITION_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source_id,
            "display_name": "Asthma",
        },
        headers=json_headers(),
    )
    missing = product_core_client.post(
        CONDITION_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": "missing-source",
            "display_name": "Asthma",
        },
        headers=json_headers(),
    )

    assert response.status_code == missing.status_code == 404
    assert response.content == missing.content
