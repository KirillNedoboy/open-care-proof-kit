from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from tests.product_core_api_support import create_candidate, create_source, json_headers


def test_person_portable_vault_export_returns_verified_zip(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client)
    candidate_id = create_candidate(product_core_client, source_id)
    assert (
        product_core_client.post(
            f"/api/product-core/v1/candidates/{candidate_id}/confirm",
            json={},
            headers=json_headers(),
        ).status_code
        == 200
    )

    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/vault-export",
        json={},
        headers=json_headers(),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="opencare-person-vault-v2.zip"'
    )
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == [
            "manifest.json",
            "manifest.sha256",
            "vault.json",
            f"sources/{source_id}/payload.bin",
        ]
        manifest = archive.read("manifest.json")
        assert archive.read("manifest.sha256") == hashlib.sha256(manifest).hexdigest().encode(
            "ascii"
        )
        vault = json.loads(archive.read("vault.json"))
    assert vault["person"]["person_id"] == "person-1"
    assert vault["format_version"] == 2
    assert "relative_path" not in response.text
    assert "visit_brief_audit_events" not in response.text


def test_person_portable_vault_export_uses_existing_error_envelope(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.post(
        "/api/product-core/v1/people/missing/vault-export",
        json={},
        headers=json_headers(),
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "person_not_found", "message": "Person was not found."}
    }
