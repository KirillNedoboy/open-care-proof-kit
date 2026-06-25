from app.pgx.coverage import CoverageSummary
from app.pgx.rule_schema import PgxFinding
from app.reports.markdown import render_markdown_report
from app.vault.schema import HealthVault


def write_doctor_briefing(
    *,
    vault: HealthVault,
    drug: str,
    findings: list[PgxFinding],
    evidence_pack_id: str,
    evidence_pack_version: str,
    coverage: CoverageSummary,
) -> str:
    return render_markdown_report(
        vault=vault,
        drug=drug,
        findings=findings,
        evidence_pack_id=evidence_pack_id,
        evidence_pack_version=evidence_pack_version,
        coverage=coverage,
    )
