from app.pgx.rule_schema import PgxFinding
from app.vault.schema import HealthVault


def render_markdown_report(
    *,
    vault: HealthVault,
    drug: str,
    findings: list[PgxFinding],
    evidence_pack_id: str,
    evidence_pack_version: str,
) -> str:
    finding_lines: list[str] = []
    source_lines: list[str] = []
    clinical_action_rule_ids = [
        finding.rule_id for finding in findings if finding.clinical_action_allowed
    ]
    if clinical_action_rule_ids:
        raise ValueError(
            "Report cannot include findings marked for clinical action: "
            + ", ".join(clinical_action_rule_ids)
        )

    if findings:
        for finding in findings:
            finding_lines.append(
                "\n".join(
                    [
                        f"### {finding.gene} / {finding.variant_rsid}",
                        f"- Genotype observed in demo data: `{finding.genotype}`",
                        f"- Evidence level: `{finding.evidence_level}`",
                        f"- Clinician review required: `{finding.clinician_review_required}`",
                        f"- Summary: {finding.summary}",
                        f"- Limitations: {finding.limitations}",
                    ]
                )
            )
            source_lines.append(f"- {finding.source_name}: {finding.source_url}")
    else:
        finding_lines.append(
            "No matching evidence-pack rule was found for this medication and demo genotype data."
        )

    current_medications = ", ".join(med.name for med in vault.medications) or "none"
    problems = ", ".join(problem.name for problem in vault.problems) or "none"
    sources = (
        "\n".join(source_lines)
        if source_lines
        else "- No matched source in demo evidence pack."
    )

    sections = [
        "# Medication-to-Doctor Briefing",
        "## Safety note",
        (
            "This report is not medical advice. It does not diagnose, prescribe, recommend "
            "dosage, or tell anyone to start or stop medication. It is a clinician-reviewable "
            "briefing generated from synthetic/demo data."
        ),
        "## Patient context used",
        f"- Patient profile: {vault.display_name}",
        f"- Data classification: {vault.data_classification}",
        f"- Age range: {vault.age_range}",
        f"- Current medications listed: {current_medications}",
        f"- Problems listed: {problems}",
        "## Medication question",
        f"What should be discussed with a clinician before or during use of `{drug}`?",
        "## Relevant findings",
        "\n".join(finding_lines),
        "## Not found / insufficient data",
        (
            "This MVP uses a small local demo evidence pack. Absence of a finding means only "
            "that no demo rule matched. It does not prove absence of pharmacogenomic relevance."
        ),
        "## Uncertain / not actionable",
        (
            "Unsupported variants, variants of uncertain significance, weak associations, "
            "and model-only predictions are not actionable in this project."
        ),
        "## Questions for clinician",
        (
            "1. Is pharmacogenomic testing or review relevant for this medication in this "
            "clinical context?"
        ),
        (
            "2. Are medication history, side-effect history, or comorbidities more important "
            "than the demo genetic finding?"
        ),
        (
            "3. Should any official guideline or drug label be reviewed before making a "
            "clinical decision?"
        ),
        "## Sources",
        sources,
        "## Audit metadata",
        f"- Evidence pack: `{evidence_pack_id}`",
        f"- Evidence pack version: `{evidence_pack_version}`",
        "- Report mode: `local-first demo`",
        "- Raw health/genetic data exported: `false`",
    ]
    return "\n\n".join(sections).strip() + "\n"
