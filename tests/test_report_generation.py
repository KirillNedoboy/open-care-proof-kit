from pathlib import Path

import pytest

from app.evidence.loader import load_evidence_pack
from app.genetics.genotype_parser import parse_23andme_file
from app.pgx.matcher import match_pgx_rules
from app.pgx.rule_schema import PgxFinding
from app.reports.json_audit import PIPELINE_STEPS, build_audit_payload
from app.reports.markdown import render_markdown_report
from app.safety.policy import evaluate_report_safety
from app.vault.loader import load_health_vault


def test_generated_report_passes_safety_policy() -> None:
    vault = load_health_vault(Path("data/demo_patients/demo_patient_a.json"))
    variants = parse_23andme_file(Path("data/demo_patients/demo_patient_a_23andme.txt"))
    pack = load_evidence_pack(Path("data/evidence_packs/pgx_demo_pack.json"))
    findings = match_pgx_rules(drug="sertraline", variants=variants, evidence_pack=pack)
    report = render_markdown_report(
        vault=vault,
        drug="sertraline",
        findings=findings,
        evidence_pack_id=pack.pack_id,
        evidence_pack_version=pack.version,
        coverage={
            "requested_drug": "sertraline",
            "evidence_pack_id": pack.pack_id,
            "evidence_pack_version": pack.version,
            "rules_for_requested_drug": 1,
            "matched_findings": 1,
            "assessed_variants": ["rs4244285"],
            "missing_rule_variants": [],
            "coverage_status": "matched_demo_rule",
        },
    )
    assert "not medical advice" in report.lower()
    assert "Sources" in report
    assert "Audit metadata" in report
    assert "Demo evidence-pack coverage" in report
    assert evaluate_report_safety(report) == []


def test_report_rejects_clinical_action_findings() -> None:
    vault = load_health_vault(Path("data/demo_patients/demo_patient_a.json"))
    finding = PgxFinding(
        rule_id="unsafe-rule",
        drug="sertraline",
        gene="CYP2C19",
        variant_rsid="rs4244285",
        genotype="AG",
        evidence_level="demo",
        summary="Demo summary.",
        limitations="Demo limitations.",
        source_name="Demo Source",
        source_url="https://example.test/source",
        clinical_action_allowed=True,
    )

    with pytest.raises(ValueError, match="clinical action"):
        render_markdown_report(
            vault=vault,
            drug="sertraline",
            findings=[finding],
            evidence_pack_id="demo",
            evidence_pack_version="0.1",
            coverage={
                "requested_drug": "sertraline",
                "evidence_pack_id": "demo",
                "evidence_pack_version": "0.1",
                "rules_for_requested_drug": 1,
                "matched_findings": 1,
                "assessed_variants": ["rs4244285"],
                "missing_rule_variants": [],
                "coverage_status": "matched_demo_rule",
            },
        )


def test_audit_payload_contains_boundary_metadata_without_raw_identifiers() -> None:
    vault = load_health_vault(Path("data/demo_patients/demo_patient_a.json"))
    audit = build_audit_payload(
        vault=vault,
        drug="sertraline",
        findings=[],
        evidence_pack_id="pgx-demo",
        evidence_pack_version="0.1",
        policy_passed=True,
        policy_violations=[],
        coverage={
            "requested_drug": "sertraline",
            "evidence_pack_id": "pgx-demo",
            "evidence_pack_version": "0.1",
            "rules_for_requested_drug": 1,
            "matched_findings": 0,
            "assessed_variants": ["rs4244285"],
            "missing_rule_variants": ["rs4244285"],
            "coverage_status": "no_matching_demo_rule",
        },
    )

    assert audit["local_first"] is True
    assert audit["demo_only"] is True
    assert audit["safety_policy_version"] == "0.1"
    assert audit["pipeline_steps"] == PIPELINE_STEPS
    assert audit["app_version"] == "0.3.0.dev0"
    assert audit["report_id"]
    assert len(audit["patient_id_hash"]) == 64
    assert "patient_id" not in audit
    assert audit["raw_health_or_genetic_data_exported"] is False
    assert audit["coverage"]["coverage_status"] == "no_matching_demo_rule"
