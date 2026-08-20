from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient

import app.main as main_module
from app.family_access.policy import OWNER_SCOPES_V2
from tests.test_product_core_documents import _text_pdf


def _upload(client: TestClient, body: bytes = b"Aspirin evidence"):
    return client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=body,
        headers={
            "content-type": "text/plain; charset=utf-8",
            "x-opencare-filename": "C:\\private\\evidence.txt",
        },
    )


def test_document_raw_upload_list_page_and_dedup(product_core_client: TestClient) -> None:
    created = _upload(product_core_client)
    assert created.status_code == 201, created.text
    document = created.json()["document"]
    assert document["source_type"] == "document"
    assert document["original_filename"] == "evidence.txt"
    assert "relative_path" not in document
    assert "payload" not in document

    duplicate = _upload(product_core_client)
    assert duplicate.status_code == 409
    assert duplicate.json()["document"]["source_id"] == document["source_id"]

    listed = product_core_client.get("/api/product-core/v1/people/person-1/documents")
    assert listed.status_code == 200
    assert len(listed.json()["documents"]) == 1

    extraction_id = document["extraction"]["extraction_id"]
    page = product_core_client.get(
        "/api/product-core/v1/people/person-1/documents/"
        f"{document['source_id']}/extractions/{extraction_id}/pages/1"
    )
    assert page.status_code == 200

    wrong_person = product_core_client.get(
        f"/api/product-core/v1/people/person-2/documents/{document['source_id']}"
    )
    assert wrong_person.status_code == 404
    assert page.json()["normalized_text"] == "Aspirin evidence"
    assert (
        product_core_client.get(
            f"/api/product-core/v1/people/person-1/documents/{document['source_id']}/download"
        ).status_code
        == 404
    )


def test_document_content_type_and_body_limits_are_narrow(product_core_client: TestClient) -> None:
    unsupported = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"x",
        headers={"content-type": "application/octet-stream"},
    )
    assert unsupported.status_code == 415

    json_mutation = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        content=b"not-json",
        headers={"content-type": "text/plain"},
    )
    assert json_mutation.status_code == 415
    assert json_mutation.json()["error"]["code"] == "json_content_type_required"

    oversized = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"",
        headers={"content-type": "text/plain", "content-length": "10485761"},
    )
    assert oversized.status_code == 413

    length_mismatch = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"two bytes",
        headers={"content-type": "text/plain", "content-length": "1"},
    )
    assert length_mismatch.status_code == 422

    pdf = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=_text_pdf("PDF evidence"),
        headers={"content-type": "application/pdf"},
    )
    assert pdf.status_code == 201, pdf.text


def test_document_locator_creates_candidate_with_exact_span(
    product_core_client: TestClient,
) -> None:
    uploaded = _upload(product_core_client)
    document = uploaded.json()["document"]
    selected = "Aspirin"
    locator = {
        "kind": "document_text_span",
        "source_id": document["source_id"],
        "content_hash": document["content_hash"],
        "extraction_id": document["extraction"]["extraction_id"],
        "page_number": 1,
        "start_codepoint": 0,
        "end_codepoint": len(selected),
        "selected_text_sha256": hashlib.sha256(selected.encode()).hexdigest(),
    }
    response = product_core_client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "person-1",
            "source_id": document["source_id"],
            "display_name": "Aspirin",
            "provenance_locator": locator,
        },
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["provenance_locator"] == locator

    locator["selected_text_sha256"] = "0" * 64
    rejected = product_core_client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "person-1",
            "source_id": document["source_id"],
            "display_name": "Aspirin",
            "provenance_locator": locator,
        },
        headers={"content-type": "application/json"},
    )
    assert rejected.status_code == 422


def test_v2_source_metadata_is_not_a_document_content_oracle(
    product_core_client: TestClient,
) -> None:
    uploaded = _upload(product_core_client)
    document = uploaded.json()["document"]
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            UPDATE person_access_assignments
            SET scopes_json = ?, scope_generation = 'family-access-v2'
            WHERE person_id = 'person-1' AND is_active = 1
            """,
            (json.dumps(sorted(OWNER_SCOPES_V2), separators=(",", ":")),),
        )

    metadata = product_core_client.get(f"/api/product-core/v1/sources/{document['source_id']}")
    assert metadata.status_code == 200
    denied_page = product_core_client.get(
        "/api/product-core/v1/people/person-1/documents/"
        f"{document['source_id']}/extractions/not-real/pages/1"
    )
    assert denied_page.status_code == 403

    denied_candidate = product_core_client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "person-1",
            "source_id": document["source_id"],
            "display_name": "Aspirin",
            "provenance_locator": {"kind": "deliberately-invalid"},
        },
        headers={"content-type": "application/json"},
    )
    assert denied_candidate.status_code == 403


def test_document_backed_review_is_denied_after_v3_scope_loss(
    product_core_client: TestClient,
) -> None:
    document = _upload(product_core_client).json()["document"]
    selected = "Aspirin"
    candidate = product_core_client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "person-1",
            "source_id": document["source_id"],
            "display_name": selected,
            "provenance_locator": {
                "kind": "document_text_span",
                "source_id": document["source_id"],
                "content_hash": document["content_hash"],
                "extraction_id": document["extraction"]["extraction_id"],
                "page_number": 1,
                "start_codepoint": 0,
                "end_codepoint": len(selected),
                "selected_text_sha256": hashlib.sha256(selected.encode()).hexdigest(),
            },
        },
        headers={"content-type": "application/json"},
    )
    assert candidate.status_code == 201
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            UPDATE person_access_assignments
            SET scopes_json = ?, scope_generation = 'family-access-v2'
            WHERE person_id = 'person-1' AND is_active = 1
            """,
            (json.dumps(sorted(OWNER_SCOPES_V2), separators=(",", ":")),),
        )

    candidate_id = candidate.json()["id"]
    for action in ("confirm", "reject", "unsupported"):
        response = product_core_client.post(
            f"/api/product-core/v1/candidates/{candidate_id}/{action}",
            json={},
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 403
