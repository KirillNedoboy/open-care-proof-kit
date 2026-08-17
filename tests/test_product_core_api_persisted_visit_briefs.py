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


def _confirmed_condition(product_core_client: TestClient) -> str:
    source = product_core_client.post(
        "/api/product-core/v1/sources/manual-condition",
        json={"person_id": "person-1", "condition": {"display_name": "Asthma"}},
        headers=json_headers(),
    )
    candidate = product_core_client.post(
        "/api/product-core/v1/candidates/conditions",
        json={
            "person_id": "person-1",
            "source_id": source.json()["source"]["source_id"],
            "display_name": "Asthma",
        },
        headers=json_headers(),
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    assert confirmed.status_code == 200
    return confirmed.json()["id"]


def _confirmed_lab(product_core_client: TestClient) -> str:
    source = product_core_client.post(
        "/api/product-core/v1/sources/manual-lab",
        json={
            "person_id": "person-1",
            "lab": {"test_name": "Hemoglobin", "result_text": "13.8", "source_flag_text": "H"},
        },
        headers=json_headers(),
    )
    candidate = product_core_client.post(
        "/api/product-core/v1/candidates/labs",
        json={
            "person_id": "person-1",
            "source_id": source.json()["source"]["source_id"],
            "test_name": "Hemoglobin",
            "result_text": "13.8",
            "source_flag_text": "H",
        },
        headers=json_headers(),
    )
    confirmed = product_core_client.post(
        f"/api/product-core/v1/candidates/{candidate.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    assert confirmed.status_code == 200
    return confirmed.json()["id"]


def test_new_brief_uses_v2_content_with_condition_and_lab_evidence(
    product_core_client: TestClient,
) -> None:
    visit_id = _visit(product_core_client)
    medication_id = _confirmed_record(product_core_client)
    condition_id = _confirmed_condition(product_core_client)
    lab_id = _confirmed_lab(product_core_client)
    product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief",
        json={},
        headers=json_headers(),
    )

    generated = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={
            "selected_record_ids": [medication_id, condition_id, lab_id],
            "expected_current_revision_number": None,
        },
        headers=json_headers(),
    )
    assert generated.status_code == 201, generated.text
    revision = generated.json()
    assert revision["content_schema_version"] == 2
    records = revision["content"]["records"]
    assert {record["fact_type"] for record in records} == {"medication", "condition", "lab"}
    by_type = {record["fact_type"]: record for record in records}
    assert by_type["medication"]["display_name"] == "Aspirin"
    assert by_type["condition"]["display_name"] == "Asthma"
    assert by_type["lab"]["test_name"] == "Hemoglobin"
    assert by_type["lab"]["source_flag_text"] == "H"
    assert by_type["lab"]["source"]["source_id"]
    assert "medications" not in revision["content"]
    assert "Medications" in revision["markdown"]
    assert "Recorded conditions" in revision["markdown"]
    assert "Recent/selected lab records" in revision["markdown"]
    # Lab flag is rendered as source-provided only.
    assert "as reported" in revision["markdown"]
    assert "Abnormal" not in revision["markdown"]
    assert "Concerning" not in revision["markdown"]

    exported = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/current:export",
        json={},
        headers=json_headers(),
    )
    assert exported.status_code == 200
    assert "Recorded conditions" in exported.text
    assert "Recent/selected lab records" in exported.text


def test_evidence_eligibility_excludes_inactive_pending_and_other_person(
    product_core_client: TestClient,
) -> None:
    visit_id = _visit(product_core_client)
    # pending medication candidate (never confirmed)
    create_candidate(product_core_client, create_source(product_core_client))
    # rejected condition
    cond_source = product_core_client.post(
        "/api/product-core/v1/sources/manual-condition",
        json={"person_id": "person-1", "condition": {"display_name": "Eczema"}},
        headers=json_headers(),
    )
    cond_candidate = product_core_client.post(
        "/api/product-core/v1/candidates/conditions",
        json={
            "person_id": "person-1",
            "source_id": cond_source.json()["source"]["source_id"],
            "display_name": "Eczema",
        },
        headers=json_headers(),
    )
    product_core_client.post(
        f"/api/product-core/v1/candidates/{cond_candidate.json()['id']}/unsupported",
        json={},
        headers=json_headers(),
    )
    # other-Person confirmed lab
    other_source = product_core_client.post(
        "/api/product-core/v1/sources/manual-lab",
        json={
            "person_id": "person-2",
            "lab": {"test_name": "Glucose", "result_text": "95"},
        },
        headers=json_headers(),
    )
    other_candidate = product_core_client.post(
        "/api/product-core/v1/candidates/labs",
        json={
            "person_id": "person-2",
            "source_id": other_source.json()["source"]["source_id"],
            "test_name": "Glucose",
            "result_text": "95",
        },
        headers=json_headers(),
    )
    other_record = product_core_client.post(
        f"/api/product-core/v1/candidates/{other_candidate.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    assert other_record.status_code == 200

    eligible = product_core_client.get(
        f"/api/product-core/v1/visits/{visit_id}/brief/evidence"
    )
    assert eligible.status_code == 200
    assert eligible.json()["evidence"] == []

    # Selecting an other-Person record is rejected.
    product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief",
        json={},
        headers=json_headers(),
    )
    invalid = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={
            "selected_record_ids": [other_record.json()["id"]],
            "expected_current_revision_number": None,
        },
        headers=json_headers(),
    )
    assert invalid.status_code == 422


def test_old_v1_revision_still_readable_and_medication_only_brief_valid(
    product_core_client: TestClient,
) -> None:
    visit_id = _visit(product_core_client)
    record_id = _confirmed_record(product_core_client)
    product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief",
        json={},
        headers=json_headers(),
    )
    generated = product_core_client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={
            "selected_record_ids": [record_id],
            "expected_current_revision_number": None,
        },
        headers=json_headers(),
    )
    assert generated.status_code == 201
    assert generated.json()["content_schema_version"] == 2
    # A medication-only v2 brief stays a valid brief.
    assert generated.json()["content"]["records"][0]["fact_type"] == "medication"
    assert "## Medications" in generated.json()["markdown"]

    # Simulate a legacy v1 revision (content key "medications",
    # content_schema_version 1, matching v1-era hash envelope) and assert it
    # is still readable.
    import hashlib as _hashlib
    import json as _json

    from app.config import get_settings
    from app.product_core.sqlite import SQLiteDatabase

    settings = get_settings()
    database = SQLiteDatabase(settings.product_db_path)
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        row = uow.connection.execute(
            "SELECT content_json, rendered_markdown FROM visit_brief_revisions "
            "WHERE revision_number = 1"
        ).fetchone()
        content = _json.loads(str(row["content_json"]))
        content["medications"] = content.pop("records")
        v1_hash = _hashlib.sha256(
            _json.dumps(
                {
                    "content_schema_version": 1,
                    "render_version": 1,
                    "content": content,
                    "rendered_markdown": str(row["rendered_markdown"]),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        uow.connection.execute(
            "UPDATE visit_brief_revisions SET content_schema_version = 1, "
            "content_json = ?, content_hash = ? WHERE revision_number = 1",
            (
                _json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                v1_hash,
            ),
        )
    legacy = product_core_client.get(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions/1"
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["content_schema_version"] == 1
    assert "Medications" in legacy.json()["markdown"]
