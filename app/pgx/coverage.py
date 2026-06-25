from typing import Literal, TypedDict

from app.evidence.pack_schema import EvidencePack
from app.pgx.rule_schema import PgxFinding

CoverageStatus = Literal[
    "matched_demo_rule",
    "no_matching_demo_rule",
    "drug_not_in_demo_pack",
]


class CoverageSummary(TypedDict):
    requested_drug: str
    evidence_pack_id: str
    evidence_pack_version: str
    rules_for_requested_drug: int
    matched_findings: int
    assessed_variants: list[str]
    missing_rule_variants: list[str]
    coverage_status: CoverageStatus


def summarize_demo_coverage(
    *,
    requested_drug: str,
    evidence_pack: EvidencePack,
    findings: list[PgxFinding],
) -> CoverageSummary:
    normalized_drug = requested_drug.strip().lower()
    relevant_rules = [rule for rule in evidence_pack.rules if rule.drug.lower() == normalized_drug]
    assessed_variants = sorted({rule.variant_rsid for rule in relevant_rules})
    matched_variants = {finding.variant_rsid for finding in findings}
    missing_rule_variants = sorted(
        variant_rsid for variant_rsid in assessed_variants if variant_rsid not in matched_variants
    )

    if findings:
        coverage_status: CoverageStatus = "matched_demo_rule"
    elif relevant_rules:
        coverage_status = "no_matching_demo_rule"
    else:
        coverage_status = "drug_not_in_demo_pack"

    return {
        "requested_drug": requested_drug,
        "evidence_pack_id": evidence_pack.pack_id,
        "evidence_pack_version": evidence_pack.version,
        "rules_for_requested_drug": len(relevant_rules),
        "matched_findings": len(findings),
        "assessed_variants": assessed_variants,
        "missing_rule_variants": missing_rule_variants,
        "coverage_status": coverage_status,
    }
