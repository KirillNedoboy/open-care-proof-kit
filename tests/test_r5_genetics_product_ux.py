"""R5.5: Genetics product UX — live Person-scoped surface boundaries.

Covers the live `/genetics` page contract: no synthetic demo content,
truthful empty states, separate genetics grants, exact upload limit,
PGx association-only semantics, bounded Research Studio, and EN/RU
localization of the workspace chrome.
"""

from __future__ import annotations

# ruff: noqa: E501
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.product_core.genetics import MAX_GENETICS_UPLOAD_BYTES, EvidenceEntry
from app.ui_localization import translate
from tests.product_core_api_support import json_headers

GENOTYPE = b"""# synthetic only\nrsDemoPGX 10 1001 AG\nrsDemoNoCall 11 1101 --\nunique-raw-marker 20 2001 CC\n"""

ALL_SCOPES = [
    "genetics.read",
    "genetics.write",
    "genetics.research",
    "genetics.compare",
    "genetics.export",
]


def _consent(client: TestClient, person_id: str, scopes: list[str] | None = None) -> None:
    response = client.post(
        f"/api/product-core/v1/people/{person_id}/genetics/consent",
        json={"confirmation": True, "scopes": scopes if scopes is not None else ALL_SCOPES},
        headers=json_headers(),
    )
    assert response.status_code == 200, response.text


def _import_genotype(
    client: TestClient,
    person_id: str,
    genome_build: str = "GRCh37/hg19",
    confirmation: bool = True,
    filename: str = "synthetic_person_a.txt",
) -> None:
    response = client.post(
        f"/api/product-core/v1/people/{person_id}/genetics/import",
        json={
            "filename": filename,
            "payload_base64": base64.b64encode(GENOTYPE).decode("ascii"),
            "genome_build": genome_build,
            "confirmation": confirmation,
        },
        headers=json_headers(),
    )
    assert response.status_code == 200, response.text


def _confirm_medication(client: TestClient, display_name: str) -> None:
    source = client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={"person_id": "person-1", "medication": {"display_name": display_name}},
        headers=json_headers(),
    )
    assert source.status_code == 201, source.text
    candidate = client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "person-1",
            "source_id": source.json()["source"]["source_id"],
            "display_name": display_name,
        },
        headers=json_headers(),
    )
    assert candidate.status_code == 201, candidate.text
    confirmed = client.post(
        f"/api/product-core/v1/candidates/{candidate.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    assert confirmed.status_code == 200, confirmed.text


# --------------------------------------------------------------------------
# A. Live / demo separation
# --------------------------------------------------------------------------


def test_genetics_page_has_no_synthetic_preview(product_core_client: TestClient) -> None:
    response = product_core_client.get("/genetics")
    assert response.status_code == 200
    for fragment in (
        "Synthetic Person A",
        "SYNTHETIC_VARIANTS",
        "demo-state",
        "synthetic-b",
        'data-genetics-mode="demo"',
    ):
        assert fragment not in response.text


def test_genetics_page_shows_empty_state_for_fresh_person(product_core_client: TestClient) -> None:
    response = product_core_client.get("/genetics")
    assert response.status_code == 200
    assert "No genetic data yet." in response.text
    assert "32,000,000" in response.text  # upload limit visible
    assert 'id="genetics-empty"' in response.text


# --------------------------------------------------------------------------
# B. Authorization
# --------------------------------------------------------------------------


def test_genetics_read_boundary(product_core_client: TestClient) -> None:
    response = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert response.status_code == 404


def test_genetics_write_boundary(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1", scopes=["genetics.read"])
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/import",
        json={
            "filename": "blocked.txt",
            "payload_base64": base64.b64encode(GENOTYPE).decode("ascii"),
            "genome_build": "GRCh37/hg19",
            "confirmation": True,
        },
        headers=json_headers(),
    )
    assert response.status_code == 404


def test_genetics_research_boundary(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1", scopes=["genetics.read", "genetics.write"])
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/research",
        json={
            "mode": "evidence",
            "question": "Is there any relevant reviewed finding?",
            "finding_ids": ["any"],
            "canonical_records": [],
            "second_person_id": None,
        },
        headers=json_headers(),
    )
    assert response.status_code == 404


def test_genetics_compare_boundary(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1", scopes=["genetics.read", "genetics.write"])
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/compare",
        json={"person_b_id": "person-2"},
        headers=json_headers(),
    )
    assert response.status_code == 404


def test_genetics_person_isolation(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1")
    _import_genotype(product_core_client, "person-1")
    visible = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert visible.status_code == 200
    hidden = product_core_client.get("/api/product-core/v1/people/person-2/genetics")
    assert hidden.status_code == 404


# --------------------------------------------------------------------------
# C. Import UX
# --------------------------------------------------------------------------


def test_genetics_upload_limit_is_exactly_32000000() -> None:
    assert MAX_GENETICS_UPLOAD_BYTES == 32_000_000


def test_genetics_import_requires_confirmation(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1")
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/import",
        json={
            "filename": "no-consent.txt",
            "payload_base64": base64.b64encode(GENOTYPE).decode("ascii"),
            "genome_build": "GRCh37/hg19",
            "confirmation": False,
        },
        headers=json_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "genetics_validation_failed"


def test_genetics_import_rejects_oversized_payload(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1")
    oversized = base64.b64encode(b"x" * (MAX_GENETICS_UPLOAD_BYTES + 1)).decode("ascii")
    response = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/import",
        json={
            "filename": "oversized.txt",
            "payload_base64": oversized,
            "genome_build": "unknown",
            "confirmation": True,
        },
        headers=json_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "genetics_validation_failed"


# --------------------------------------------------------------------------
# D. Findings / PGx
# --------------------------------------------------------------------------


def test_genetics_pgx_has_no_dosage_or_start_stop(
    product_core_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.product_core.genetics import GeneticsService

    monkeypatch.setattr(
        GeneticsService,
        "_load_evidence_entries",
        lambda self: [
            EvidenceEntry(
                evidence_id="pgx-test-med",
                pack_id="genetics-test-pack",
                pack_version="1.0.0",
                rsid="rsDemoPGX",
                chromosome="10",
                position=1001,
                gene="DEMO1",
                genome_build="GRCh37/hg19",
                genotype_condition="AG",
                category="pgx",
                title="Test PGx medication association",
                association="Altered metabolism association",
                evidence_level="Moderate",
                source_name="Test guideline",
                source_citation="Test citation",
                source_url=None,
                limitations=("Association only.", "Not prescribing advice."),
                orientation_metadata="resolved",
                medication_names=("demomed",),
            )
        ],
    )
    _consent(product_core_client, "person-1")
    _import_genotype(product_core_client, "person-1")
    _confirm_medication(product_core_client, "DemoMed")

    overview = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert overview.status_code == 200, overview.text
    findings = overview.json()["findings"]
    pgx_finding = next(f for f in findings if f["evidence_id"] == "pgx-test-med")
    reviewed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/genetics/findings/{pgx_finding['finding_id']}/review",
        json={"status": "reviewed", "reason": "Synthetic review for boundary test"},
        headers=json_headers(),
    )
    assert reviewed.status_code == 200, reviewed.text

    after = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    intersections = after.json()["pgx_intersections"]
    assert intersections, "expected a PGx intersection after medication match"
    assert all(item["action"] == "association_only" for item in intersections)
    assert all(item["medication_name"] == "demomed" for item in intersections)


def test_genetics_findings_machine_status_values_unchanged(
    product_core_client: TestClient,
) -> None:
    _consent(product_core_client, "person-1")
    _import_genotype(product_core_client, "person-1")
    overview = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    assert overview.status_code == 200, overview.text
    payload = overview.json()
    assert payload["dataset"]["genome_build"] == "GRCh37/hg19"
    assert {finding["status"] for finding in payload["findings"]} <= {
        "pending",
        "reviewed",
        "dismissed",
        "unsupported",
        "conflicting",
    }
    assert "rsDemoPGX" in overview.text
    assert "unique-raw-marker" not in overview.text


# --------------------------------------------------------------------------
# E. Research Studio
# --------------------------------------------------------------------------


def test_genetics_research_evidence_mode_rejects_speculation(
    product_core_client: TestClient,
) -> None:
    _consent(product_core_client, "person-1")
    _import_genotype(product_core_client, "person-1")
    overview = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    finding_id = overview.json()["findings"][0]["finding_id"]
    reviewed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/genetics/findings/{finding_id}/review",
        json={"status": "reviewed", "reason": "Synthetic review"},
        headers=json_headers(),
    )
    assert reviewed.status_code == 200, reviewed.text

    result = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/research",
        json={
            "mode": "evidence",
            "question": "What does the reviewed association support?",
            "finding_ids": [finding_id],
            "canonical_records": [],
            "second_person_id": None,
        },
        headers=json_headers(),
    )
    assert result.status_code == 200, result.text
    output = result.json()["output"]
    assert output["confidence"] == "supported"
    assert all(
        claim["epistemic_status"] not in {"plausible", "speculative"}
        for claim in output["claims"]
    )


def test_genetics_research_raw_genome_never_included(product_core_client: TestClient) -> None:
    _consent(product_core_client, "person-1")
    _import_genotype(product_core_client, "person-1")
    overview = product_core_client.get("/api/product-core/v1/people/person-1/genetics")
    finding_id = overview.json()["findings"][0]["finding_id"]
    reviewed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/genetics/findings/{finding_id}/review",
        json={"status": "reviewed", "reason": "Synthetic review"},
        headers=json_headers(),
    )
    assert reviewed.status_code == 200, reviewed.text

    result = product_core_client.post(
        "/api/product-core/v1/people/person-1/genetics/research",
        json={
            "mode": "explore",
            "question": "List alternative explanations.",
            "finding_ids": [finding_id],
            "canonical_records": [],
            "second_person_id": None,
        },
        headers=json_headers(),
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["packet"]["raw_genome_included"] is False
    assert "unique-raw-marker" not in result.text
    assert payload["packet"]["context_hash"]


# --------------------------------------------------------------------------
# F. Localization
# --------------------------------------------------------------------------


def test_genetics_page_localized_en_and_ru(product_core_client: TestClient) -> None:
    english = product_core_client.get("/genetics")
    assert english.status_code == 200
    assert "Genetics" in english.text
    assert "No genetic data yet." in english.text

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/genetics")
    assert russian.status_code == 200
    assert "Генетика" in russian.text
    assert "Генетических данных пока нет." in russian.text


def test_genetics_machine_identifiers_not_translated(product_core_client: TestClient) -> None:
    for identifier in ("rs1234567", "CYP2C19", "GRCh37/hg19", "genetics.read", "genetics.write"):
        assert translate("en", identifier) == identifier
        assert translate("ru", identifier) == identifier

    english = product_core_client.get("/genetics")
    assert "GRCh37/hg19" in english.text
    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian = product_core_client.get("/genetics")
    assert "GRCh37/hg19" in russian.text


def test_genetics_tabs_activate_on_click() -> None:
    script = Path("app/static/genetics.js").read_text(encoding="utf-8")
    assert 'tabList?.addEventListener("click"' in script
    assert 'activateTab(clickedTab.dataset.tab)' in script
