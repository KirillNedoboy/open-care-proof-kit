from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.product_core.portable_vault_export import PORTABLE_VAULT_FORMAT_VERSION
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
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="opencare-person-vault-v{PORTABLE_VAULT_FORMAT_VERSION}.zip"'
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
    assert vault["format_version"] == 4
    assert "relative_path" not in response.text
    assert "visit_brief_audit_events" not in response.text


def test_vault_download_filename_version_matches_format_version(
    product_core_client: TestClient,
) -> None:
    """The server Content-Disposition filename version must track the portable
    vault format version — no hand-written "v2"/"v3" literal drift."""
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/vault-export",
        json={},
        headers=json_headers(),
    )

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert (
        disposition
        == f'attachment; filename="opencare-person-vault-v{PORTABLE_VAULT_FORMAT_VERSION}.zip"'
    )
    assert f"v{PORTABLE_VAULT_FORMAT_VERSION}.zip" in disposition
    assert PORTABLE_VAULT_FORMAT_VERSION == 4
    assert "opencare-person-vault-v4.zip" in disposition

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
