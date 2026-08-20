"""Synthetic evidence-pack loading, matching, coverage, and PGx intersection."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app.genetics.models import (
    CandidateFinding,
    CoverageReport,
    CoverageState,
    EvidenceAssessment,
    EvidenceCategory,
    EvidenceEntry,
    GeneticsEvidencePack,
    GenomeBuild,
    GenotypeObservation,
    OrientationState,
    PgxMedicationIntersection,
)


def load_genetics_evidence_pack(path: Path) -> GeneticsEvidencePack:
    """Load and validate a local, explicitly synthetic genetics evidence pack."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load genetics evidence pack: {path}") from exc
    return GeneticsEvidencePack.model_validate(payload)


def assess_evidence(
    observations: Iterable[GenotypeObservation],
    pack: GeneticsEvidencePack,
) -> tuple[EvidenceAssessment, ...]:
    """Assess every evidence target and emit findings only for safe exact matches."""

    ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
    return tuple(_assess_entry(ordered, entry) for entry in pack.entries)


def summarize_coverage(assessments: Iterable[EvidenceAssessment]) -> CoverageReport:
    """Count mutually exclusive deterministic coverage outcomes."""

    items = tuple(assessments)
    counts = Counter(item.coverage for item in items)
    return CoverageReport(
        target=len(items),
        present=counts[CoverageState.PRESENT],
        no_call=counts[CoverageState.NO_CALL],
        not_present=counts[CoverageState.NOT_PRESENT],
        build_incompatible=counts[CoverageState.BUILD_INCOMPATIBLE],
        unresolved=counts[CoverageState.UNRESOLVED],
    )


def intersect_pgx_medications(
    *,
    findings: Iterable[CandidateFinding],
    evidence_entries: Iterable[EvidenceEntry],
    confirmed_normalized_medications: Iterable[str],
) -> tuple[PgxMedicationIntersection, ...]:
    """Intersect reviewed/candidate PGx findings with exact normalized medication names."""

    evidence_by_id = {entry.evidence_id: entry for entry in evidence_entries}
    medication_by_key = {
        medication.strip().casefold(): medication
        for medication in confirmed_normalized_medications
        if medication.strip()
    }
    intersections: list[PgxMedicationIntersection] = []
    for finding in sorted(findings, key=lambda item: item.finding_id):
        entry = evidence_by_id.get(finding.evidence_id)
        if entry is None or entry.category is not EvidenceCategory.PGX:
            continue
        for evidence_medication in sorted(entry.medication_names, key=str.casefold):
            medication = medication_by_key.get(evidence_medication.strip().casefold())
            if medication is None:
                continue
            intersections.append(
                PgxMedicationIntersection(
                    finding_id=finding.finding_id,
                    evidence_id=entry.evidence_id,
                    gene=entry.gene,
                    medication_name=medication,
                    association=entry.association,
                    evidence_level=entry.evidence_level,
                    source_name=entry.source_name,
                    citation=entry.citation,
                    limitations=entry.limitations,
                )
            )
    return tuple(intersections)


def _assess_entry(
    observations: tuple[GenotypeObservation, ...],
    entry: EvidenceEntry,
) -> EvidenceAssessment:
    candidates = [observation for observation in observations if _same_target(observation, entry)]
    if not candidates:
        return EvidenceAssessment(evidence_id=entry.evidence_id, coverage=CoverageState.NOT_PRESENT)
    observation = candidates[0]
    if observation.no_call:
        return EvidenceAssessment(
            evidence_id=entry.evidence_id,
            observation_id=observation.observation_id,
            coverage=CoverageState.NO_CALL,
        )
    if not _build_compatible(observation.genome_build, entry.genome_build):
        return EvidenceAssessment(
            evidence_id=entry.evidence_id,
            observation_id=observation.observation_id,
            coverage=CoverageState.BUILD_INCOMPATIBLE,
        )
    if not _orientation_compatible(observation.orientation, entry.orientation_required):
        return EvidenceAssessment(
            evidence_id=entry.evidence_id,
            observation_id=observation.observation_id,
            coverage=CoverageState.UNRESOLVED,
        )
    if observation.normalized_genotype not in entry.matching_genotypes:
        return EvidenceAssessment(
            evidence_id=entry.evidence_id,
            observation_id=observation.observation_id,
            coverage=CoverageState.PRESENT,
        )

    identity = f"{observation.observation_id}|{entry.evidence_id}"
    finding = CandidateFinding(
        finding_id=f"finding-{sha256(identity.encode('utf-8')).hexdigest()[:20]}",
        observation_id=observation.observation_id,
        evidence_id=entry.evidence_id,
        gene=entry.gene,
        normalized_genotype=observation.normalized_genotype,
        category=entry.category,
        evidence_level=entry.evidence_level,
        association=entry.association,
        limitations=entry.limitations,
    )
    return EvidenceAssessment(
        evidence_id=entry.evidence_id,
        observation_id=observation.observation_id,
        coverage=CoverageState.PRESENT,
        finding=finding,
    )


def _same_target(observation: GenotypeObservation, entry: EvidenceEntry) -> bool:
    if entry.safe_rsid_match and entry.rsid and observation.rsid == entry.rsid:
        return True
    return (
        entry.chromosome is not None
        and entry.position is not None
        and observation.chromosome == entry.chromosome
        and observation.position == entry.position
    )


def _build_compatible(left: GenomeBuild, right: GenomeBuild) -> bool:
    return left is right and left is not GenomeBuild.UNKNOWN


def _orientation_compatible(observed: OrientationState, required: OrientationState) -> bool:
    if required is OrientationState.NOT_APPLICABLE:
        return observed in {OrientationState.NOT_APPLICABLE, OrientationState.RESOLVED}
    return observed is OrientationState.RESOLVED
