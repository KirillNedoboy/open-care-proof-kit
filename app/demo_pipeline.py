from dataclasses import dataclass
from typing import Any

from app.ai.report_writer import write_doctor_briefing
from app.config import get_settings
from app.evidence.loader import load_evidence_pack
from app.genetics.genotype_parser import parse_23andme_file
from app.pgx.matcher import match_pgx_rules
from app.reports.json_audit import PIPELINE_STEPS as PIPELINE_STEPS
from app.reports.json_audit import build_audit_payload
from app.safety.policy import evaluate_report_safety
from app.vault.loader import load_health_vault


@dataclass(frozen=True)
class DemoBriefingResult:
    report_markdown: str
    audit: dict[str, Any]
    findings_count: int
    policy_passed: bool
    policy_violations: list[str]


def build_demo_briefing(drug: str) -> DemoBriefingResult:
    settings = get_settings()

    patient_path = settings.data_dir / "demo_patients" / "demo_patient_a.json"
    genotype_path = settings.data_dir / "demo_patients" / "demo_patient_a_23andme.txt"
    evidence_path = settings.data_dir / "evidence_packs" / "pgx_demo_pack.json"

    vault = load_health_vault(patient_path)
    variants = parse_23andme_file(genotype_path, genome_build="demo-build")
    evidence_pack = load_evidence_pack(evidence_path)
    findings = match_pgx_rules(drug=drug, variants=variants, evidence_pack=evidence_pack)
    report = write_doctor_briefing(
        vault=vault,
        drug=drug,
        findings=findings,
        evidence_pack_id=evidence_pack.pack_id,
        evidence_pack_version=evidence_pack.version,
    )
    violations = evaluate_report_safety(report)
    policy_violations = [violation.code for violation in violations]
    audit = build_audit_payload(
        vault=vault,
        drug=drug,
        findings=findings,
        evidence_pack_id=evidence_pack.pack_id,
        evidence_pack_version=evidence_pack.version,
        policy_passed=not violations,
        policy_violations=policy_violations,
    )

    return DemoBriefingResult(
        report_markdown=report,
        audit=audit,
        findings_count=len(findings),
        policy_passed=not violations,
        policy_violations=policy_violations,
    )
