from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app import __version__
from app.pgx.rule_schema import PgxFinding
from app.vault.schema import HealthVault

PIPELINE_STEPS = [
    "vault_loaded",
    "genotype_parsed",
    "evidence_pack_loaded",
    "rules_matched",
    "report_rendered",
    "safety_checked",
]


def hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_audit_payload(
    *,
    vault: HealthVault,
    drug: str,
    findings: list[PgxFinding],
    evidence_pack_id: str,
    evidence_pack_version: str,
    policy_passed: bool,
    policy_violations: list[str],
) -> dict[str, Any]:
    patient_id_hash = hash_text(vault.patient_id)
    finding_rule_ids = [finding.rule_id for finding in findings]
    report_id = hash_text(
        "|".join(
            [
                patient_id_hash,
                drug,
                evidence_pack_id,
                evidence_pack_version,
                ",".join(finding_rule_ids),
            ]
        )
    )

    return {
        "audit_version": "0.1",
        "app_version": __version__,
        "report_id": report_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "local_first": True,
        "demo_only": vault.data_classification == "synthetic_demo_only",
        "pipeline_steps": PIPELINE_STEPS,
        "safety_policy_version": "0.1",
        "patient_id_hash": patient_id_hash,
        "data_classification": vault.data_classification,
        "drug": drug,
        "findings_count": len(findings),
        "finding_rule_ids": finding_rule_ids,
        "evidence_pack_id": evidence_pack_id,
        "evidence_pack_version": evidence_pack_version,
        "policy_passed": policy_passed,
        "policy_violations": policy_violations,
        "llm_mode": "local_report_writer_stub",
        "raw_health_or_genetic_data_exported": False,
    }
