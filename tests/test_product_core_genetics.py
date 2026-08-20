from __future__ import annotations

# ruff: noqa: E501
import base64
import json
from pathlib import Path

import pytest

from app.product_core.genetics import (
    MAX_GENETICS_UPLOAD_BYTES,
    GeneticsService,
    GeneticsValidationError,
    decode_bounded_genetics_base64,
)
from app.product_core.services import PeopleService, SourceService
from app.product_core.sqlite import SQLiteDatabase

SYNTHETIC_GENOTYPE = b"""# rsid chromosome position genotype\nrsDemoPGX 10 1001 AG\nrsDemoNoCall 11 1101 --\nrsDemoAmbiguous 12 1201 AT\nunique-raw-marker 20 2001 CC\n"""


def _service(tmp_path: Path) -> tuple[GeneticsService, SQLiteDatabase, str]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    people = PeopleService(database, id_factory=lambda: "person-id")
    person = people.create("Synthetic Person A")
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO actors(actor_id, username_normalized, display_name, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            ("actor-id", "actor", "Synthetic Actor", "2026-08-20T00:00:00+00:00"),
        )
    sources = SourceService(database, tmp_path / "sources", id_factory=lambda: "source-id")
    service = GeneticsService(
        database,
        sources,
        Path("data"),
        id_factory=iter(
            [
                "dataset-id",
                "observation-pgx",
                "finding-pgx",
                "observation-nocall",
                "observation-ambiguous",
                "review-id",
                "session-id",
                "claim-id",
            ]
        ).__next__,
    )
    return service, database, person.person_id


def test_import_selectively_indexes_and_preserves_coverage_boundary(tmp_path: Path) -> None:
    service, database, person_id = _service(tmp_path)

    result = service.import_consumer_genotype(
        person_id=person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic_person_a.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )

    assert result.parsed_loci_count == 4
    assert result.indexed_loci_count == 3
    assert result.findings_count == 1
    overview = service.overview(person_id=person_id)
    assert overview["coverage"]["not_present_loci"] >= 1
    assert all("unique-raw-marker" not in json.dumps(item) for item in overview["observations"])
    assert overview["findings"][0]["status"] == "pending"
    with database.connect() as connection:
        assert connection.execute("SELECT source_type FROM sources").fetchone()[0] == "genetics"


def test_review_and_research_preserve_epistemic_contract(tmp_path: Path) -> None:
    service, _database, person_id = _service(tmp_path)
    service.import_consumer_genotype(
        person_id=person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic_person_a.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )
    finding_id = service.overview(person_id=person_id)["findings"][0]["finding_id"]
    service.review_finding(
        finding_id=finding_id,
        person_id=person_id,
        actor_id="actor-id",
        status="reviewed",
        reason="Synthetic reviewer approval",
    )
    packet = service.build_research_packet(
        person_id=person_id,
        finding_ids=[finding_id],
        canonical_records=[{"id": "med-1", "kind": "medication", "display_name": "DemoMed"}],
    )
    result = service.run_deterministic_research(
        person_id=person_id,
        actor_id="actor-id",
        mode="explore",
        question="What alternative explanations should be investigated?",
        packet=packet,
    )
    assert result["packet"]["raw_genome_included"] is False
    assert result["output"]["claims"][0]["epistemic_status"] == "plausible"
    assert result["output"]["evidence_against"]


def test_research_rejects_invented_citation_and_unconfirmed_import(tmp_path: Path) -> None:
    service, _database, person_id = _service(tmp_path)
    try:
        service.import_consumer_genotype(
            person_id=person_id,
            payload=SYNTHETIC_GENOTYPE,
            original_filename="synthetic_person_a.txt",
            confirmation=False,
        )
    except GeneticsValidationError as exc:
        assert str(exc) == "genetics_import_confirmation_required"
    else:
        raise AssertionError("unconfirmed genetics import must fail")
    service.import_consumer_genotype(
        person_id=person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic_person_a.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )
    finding_id = service.overview(person_id=person_id)["findings"][0]["finding_id"]
    service.review_finding(
        finding_id=finding_id,
        person_id=person_id,
        actor_id="actor-id",
        status="reviewed",
        reason=None,
    )
    packet = service.build_research_packet(person_id=person_id, finding_ids=[finding_id])
    output = {
        "what_may_be_happening": "x",
        "evidence_supporting": ["not-supplied"],
        "evidence_against": ["counter"],
        "alternative_explanations": ["x"],
        "missing_information": ["x"],
        "confidence": "plausible",
        "questions_worth_investigating": ["x"],
        "claims": [
            {
                "claim": "x",
                "epistemic_status": "speculative",
                "supporting_evidence_ids": ["not-supplied"],
                "contradicting_evidence_ids": [],
                "person_record_ids": [],
                "reasoning_summary": "x",
            }
        ],
    }
    try:
        service.validate_research_output(output, packet, mode="explore")
    except GeneticsValidationError as exc:
        assert str(exc) == "invalid_genetics_citation"
    else:
        raise AssertionError("invented citations must fail closed")


def test_genetics_export_is_explicit_and_ordinary_vault_excludes_raw_source(
    tmp_path: Path,
) -> None:
    from io import BytesIO
    from zipfile import ZipFile

    from app.product_core.portable_vault_export import PortableVaultExportService

    service, database, person_id = _service(tmp_path)
    service.import_consumer_genotype(
        person_id=person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic_person_a.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )
    genetics_package = service.export_package(person_id=person_id)
    with ZipFile(BytesIO(genetics_package)) as archive:
        assert b"unique-raw-marker" in archive.read("source/payload.txt")
        assert archive.read("manifest.json").find(b"OpenCare Genetics Package v1") >= 0
    ordinary = PortableVaultExportService(database, service.sources.store).export(person_id)
    import json

    ordinary_payload = json.loads(ordinary.vault_json)
    assert all(source["source_type"] != "genetics" for source in ordinary_payload["sources"])


def test_base64_boundary_and_failed_import_cleanup(tmp_path: Path) -> None:
    accepted = base64.b64encode(b"x" * MAX_GENETICS_UPLOAD_BYTES).decode("ascii")
    assert len(decode_bounded_genetics_base64(accepted)) == MAX_GENETICS_UPLOAD_BYTES
    with pytest.raises(GeneticsValidationError):
        decode_bounded_genetics_base64(
            base64.b64encode(b"x" * (MAX_GENETICS_UPLOAD_BYTES + 1)).decode("ascii")
        )
    with pytest.raises(GeneticsValidationError):
        decode_bounded_genetics_base64("not-base64")

    service, database, person_id = _service(tmp_path)
    broken = GeneticsService(
        database,
        service.sources,
        Path("data"),
        id_factory=iter(["dataset-only"]).__next__,
    )
    with pytest.raises(StopIteration):
        broken.import_consumer_genotype(
            person_id=person_id,
            payload=SYNTHETIC_GENOTYPE,
            original_filename="synthetic_failed.txt",
            genome_build="GRCh37/hg19",
            confirmation=True,
        )
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM genetic_datasets").fetchone()[0] == 0


def test_product_core_research_rejects_diagnosis_and_prescriptions(tmp_path: Path) -> None:
    service, _database, _person_id = _service(tmp_path)
    packet = {"findings": [], "canonical_records": [], "raw_genome_included": False}
    base = {
        "what_may_be_happening": "bounded",
        "evidence_supporting": [],
        "evidence_against": ["coverage is incomplete"],
        "alternative_explanations": ["coincidence"],
        "missing_information": ["confirmation"],
        "confidence": "plausible",
        "questions_worth_investigating": ["what would change confidence?"],
    }
    for framing in ("external claim: ", "literature says: ", "quoted claim: "):
        for text in (
            "You have disease X.",
            "These variants confirm disease X.",
            "This proves that your symptoms are caused by X.",
            "Start treatment Y.",
            "Stop treatment Y.",
            "Change medication X to Y.",
            "Increase medication to 10 mg.",
            "Decrease medication to 5 mg.",
        ):
            with pytest.raises(GeneticsValidationError):
                service.validate_research_output(
                    {
                        **base,
                        "claims": [
                            {
                                "claim": framing + text,
                                "epistemic_status": "plausible",
                                "reasoning_summary": "context",
                            }
                        ],
                    },
                    packet,
                    mode="explore",
                )
