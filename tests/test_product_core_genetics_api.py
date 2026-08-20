from __future__ import annotations

# ruff: noqa: E501
import base64

from fastapi.testclient import TestClient

from tests.product_core_api_support import json_headers

GENOTYPE = b"""# synthetic only\nrsDemoPGX 10 1001 AG\nrsDemoNoCall 11 1101 --\nunique-raw-marker 20 2001 CC\n"""
SCOPES = [
    "genetics.read",
    "genetics.write",
    "genetics.research",
    "genetics.compare",
    "genetics.export",
]


def _consent(client: TestClient, person_id: str) -> None:
    response = client.post(
        f"/api/product-core/v1/people/{person_id}/genetics/consent",
        json={"confirmation": True, "scopes": SCOPES},
        headers=json_headers(),
    )
    assert response.status_code == 200, response.text


def test_genetics_requires_explicit_consent_and_excludes_raw_marker(
    product_core_client: TestClient,
) -> None:
    denied = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert denied.status_code == 404

    _consent(product_core_client, "person-1")
    imported = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/import",
        json={
            "filename": "synthetic_person_a.txt",
            "payload_base64": base64.b64encode(GENOTYPE).decode("ascii"),
            "genome_build": "GRCh37/hg19",
            "confirmation": True,
        },
        headers=json_headers(),
    )
    assert imported.status_code == 200, imported.text
    workspace = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    assert payload["dataset"]["genome_build"] == "GRCh37/hg19"
    assert payload["coverage"]["not_present_loci"] >= 1
    assert "unique-raw-marker" not in workspace.text


def test_genetics_access_is_person_isolated_and_comparison_needs_both_grants(
    product_core_client: TestClient,
) -> None:
    _consent(product_core_client, "person-1")
    hidden = product_core_client.get("/api/product-core/v1/people/person-2/genetics")
    assert hidden.status_code == 404
    comparison = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/compare",
        json={"person_b_id": "person-2"},
        headers=json_headers(),
    )
    assert comparison.status_code == 404
