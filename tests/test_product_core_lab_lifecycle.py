from __future__ import annotations

from fastapi.testclient import TestClient

from tests.product_core_api_support import json_headers

LAB_SOURCE_PATH = "/api/product-core/v1/sources/manual-lab"
LAB_CANDIDATE_PATH = "/api/product-core/v1/candidates/labs"
LABS_PATH = "/api/product-core/v1/people/person-1/labs"


def create_lab_source(
    client: TestClient,
    person_id: str = "person-1",
    test_name: str = "Hemoglobin",
    *,
    result_text: str = "13.8",
    unit_text: str | None = "g/dL",
    source_flag_text: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "person_id": person_id,
        "lab": {
            "test_name": test_name,
            "result_text": result_text,
            "unit_text": unit_text,
        },
    }
    if source_flag_text is not None:
        payload["lab"]["source_flag_text"] = source_flag_text  # type: ignore[index]
    response = client.post(LAB_SOURCE_PATH, json=payload, headers=json_headers())
    assert response.status_code == 201, response.text
    return response.json()["source"]["source_id"]


def create_lab_candidate(
    client: TestClient,
    source_id: str,
    *,
    person_id: str = "person-1",
    test_name: str = "Hemoglobin",
    result_text: str = "13.8",
    unit_text: str | None = "g/dL",
    source_flag_text: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "person_id": person_id,
        "source_id": source_id,
        "test_name": test_name,
        "result_text": result_text,
        "unit_text": unit_text,
    }
    if source_flag_text is not None:
        payload["source_flag_text"] = source_flag_text
    response = client.post(LAB_CANDIDATE_PATH, json=payload, headers=json_headers())
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_lab_lifecycle_preserves_source_values_and_confirms(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(
        product_core_client,
        test_name="Hemoglobin",
        result_text="13.8",
        unit_text="g/dL",
        source_flag_text="H",
    )
    candidate_id = create_lab_candidate(
        product_core_client,
        source_id,
        test_name="Hemoglobin",
        result_text="13.8",
        source_flag_text="H",
    )

    detail = product_core_client.get(
        f"/api/product-core/v1/candidates/labs/{candidate_id}"
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    records = product_core_client.get(LABS_PATH)
    timeline = product_core_client.get("/api/product-core/v1/people/person-1/timeline")

    # Source-preserving values: result_text stays text, the flag is the
    # source-provided value verbatim (never OpenCare-derived).
    assert detail.json()["fact_type"] == "lab"
    assert detail.json()["test_name"] == "Hemoglobin"
    assert detail.json()["result_text"] == "13.8"
    assert detail.json()["unit_text"] == "g/dL"
    assert detail.json()["source_flag_text"] == "H"
    assert detail.json()["provenance_locator"] == {
        "kind": "structured_field",
        "path": "data.lab.test_name",
    }
    assert confirmed.status_code == 200
    record = records.json()["labs"][0]
    assert record["test_name"] == "Hemoglobin"
    assert record["result_text"] == "13.8"
    assert record["source_flag_text"] == "H"
    assert record["is_active"] is True
    assert timeline.json()["events"][0]["event_type"] == "lab_confirmed"
    assert timeline.json()["events"][0]["title"] == "Lab confirmed: Hemoglobin"


def test_lab_without_source_flag_never_derives_one(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(product_core_client, result_text="normal")
    candidate_id = create_lab_candidate(
        product_core_client, source_id, result_text="normal"
    )

    detail = product_core_client.get(
        f"/api/product-core/v1/candidates/labs/{candidate_id}"
    )

    # No flag was provided: no inference (null), even though the result text
    # reads "normal". OpenCare never classifies lab values.
    assert detail.json()["source_flag_text"] is None
    assert "normal" in detail.json()["result_text"]


def test_lab_reject_and_unsupported_create_no_canonical(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(product_core_client, test_name="Glucose")
    rejected_id = create_lab_candidate(
        product_core_client, source_id, test_name="Glucose"
    )
    unsupported_id = create_lab_candidate(
        product_core_client, source_id, test_name="Glucose"
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

    assert rejected.json()["status"] == "rejected"
    assert unsupported.json()["status"] == "unsupported"
    assert product_core_client.get(LABS_PATH).json() == {"labs": []}


def test_lab_duplicate_confirm_creates_single_canonical(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(product_core_client)
    candidate_id = create_lab_candidate(product_core_client, source_id)

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

    assert first.json() == second.json()
    assert len(product_core_client.get(LABS_PATH).json()["labs"]) == 1
    assert len(
        product_core_client.get("/api/product-core/v1/people/person-1/timeline").json()["events"]
    ) == 1


def test_lab_correction_supersedes_canonical_with_lineage(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(product_core_client, result_text="13.8")
    candidate_id = create_lab_candidate(
        product_core_client, source_id, result_text="13.8"
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    old_record_id = confirmed.json()["id"]

    corrected_source = create_lab_source(
        product_core_client, result_text="14.1", source_flag_text="H"
    )
    replacement = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/correct:lab",
        json={
            "test_name": "Hemoglobin",
            "result_text": "14.1",
            "source_flag_text": "H",
            "source_id": corrected_source,
        },
        headers=json_headers(),
    )
    assert replacement.status_code == 201
    assert replacement.json()["predecessor_candidate_id"] == candidate_id
    corrected = product_core_client.post(
        f"/api/product-core/v1/candidates/{replacement.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    new_record_id = corrected.json()["id"]

    records = product_core_client.get(LABS_PATH + "?include_inactive=true").json()["labs"]
    by_id = {record["id"]: record for record in records}
    assert by_id[old_record_id]["is_active"] is False
    assert by_id[old_record_id]["superseded_by_record_id"] == new_record_id
    assert by_id[new_record_id]["is_active"] is True
    assert by_id[new_record_id]["result_text"] == "14.1"
    assert by_id[new_record_id]["provenance_locator"] == {
        "kind": "structured_field",
        "path": "data.lab.test_name",
    }
    assert by_id[new_record_id]["predecessor_candidate_id"] == candidate_id

    events = product_core_client.get(
        "/api/product-core/v1/people/person-1/timeline"
    ).json()["events"]
    event_types = {(event["event_type"], event["canonical_record_id"]) for event in events}
    assert ("lab_confirmed", new_record_id) in event_types
    assert ("lab_corrected", old_record_id) in event_types


def test_lab_person_isolation_and_missing_ids(
    product_core_client: TestClient,
) -> None:
    source_id = create_lab_source(product_core_client, person_id="person-1")
    candidate_id = create_lab_candidate(product_core_client, source_id)
    product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )

    other = product_core_client.get("/api/product-core/v1/people/person-2/labs")
    missing = product_core_client.get("/api/product-core/v1/labs/missing-record")
    missing_candidate = product_core_client.get(
        "/api/product-core/v1/candidates/labs/missing-candidate"
    )

    assert other.json() == {"labs": []}
    assert missing.status_code == 404
    assert missing_candidate.status_code == 404


def test_plain_text_lab_candidate_requires_valid_span_locator(
    product_core_client: TestClient,
) -> None:
    source = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "Glucose 95 mg/dL"},
        headers=json_headers(),
    ).json()["source"]

    without_locator = product_core_client.post(
        LAB_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source["source_id"],
            "test_name": "Glucose",
        },
        headers=json_headers(),
    )
    assert without_locator.status_code == 422
    assert without_locator.json()["error"]["code"] == "provenance_validation_failed"

    wrong_span = product_core_client.post(
        LAB_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source["source_id"],
            "test_name": "Glucose",
            "provenance_locator": {"kind": "span", "start": 50, "end": 60},
        },
        headers=json_headers(),
    )
    assert wrong_span.status_code == 422

    valid = product_core_client.post(
        LAB_CANDIDATE_PATH,
        json={
            "person_id": "person-1",
            "source_id": source["source_id"],
            "test_name": "Glucose",
            "provenance_locator": {"kind": "span", "start": 0, "end": 7},
        },
        headers=json_headers(),
    )
    assert valid.status_code == 201
