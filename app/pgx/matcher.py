from app.evidence.pack_schema import EvidencePack
from app.genetics.normalizer import NormalizedVariant
from app.pgx.rule_schema import PgxFinding


def match_pgx_rules(
    *,
    drug: str,
    variants: list[NormalizedVariant],
    evidence_pack: EvidencePack,
) -> list[PgxFinding]:
    normalized_drug = drug.strip().lower()
    variants_by_rsid = {
        variant.rsid.lower(): variant
        for variant in variants
        if variant.rsid and not variant.no_call
    }

    findings: list[PgxFinding] = []

    for rule in evidence_pack.rules:
        if rule.drug.lower() != normalized_drug:
            continue

        variant = variants_by_rsid.get(rule.variant_rsid.lower())
        if variant is None:
            continue

        if variant.genotype.upper() not in {g.upper() for g in rule.matching_genotypes}:
            continue

        findings.append(
            PgxFinding(
                rule_id=rule.rule_id,
                drug=rule.drug,
                gene=rule.gene,
                variant_rsid=rule.variant_rsid,
                genotype=variant.genotype,
                evidence_level=rule.evidence_level,
                summary=rule.summary,
                limitations=rule.limitations,
                source_name=rule.source_name,
                source_url=str(rule.source_url),
                clinician_review_required=rule.clinician_review_required,
                clinical_action_allowed=rule.clinical_action_allowed,
            )
        )

    return findings
