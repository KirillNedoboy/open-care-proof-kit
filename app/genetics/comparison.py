"""Deterministic identity-by-state comparison over selected observations."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from pydantic import Field

from app.genetics.models import FrozenModel, GenomeBuild, GenotypeObservation, OrientationState


class IbsComparison(FrozenModel):
    """Coverage-aware IBS counts; similarity is absent when nothing is comparable."""

    common_loci: int = Field(ge=0)
    differing_genotypes: int = Field(ge=0)
    ibs0: int = Field(ge=0)
    ibs1: int = Field(ge=0)
    ibs2: int = Field(ge=0)
    no_call_loci: int = Field(ge=0)
    missing_loci: int = Field(ge=0)
    incompatible_loci: int = Field(ge=0)
    similarity: float | None
    insufficient_coverage: bool
    limitations: tuple[str, ...]


def compare_ibs(
    left: Iterable[GenotypeObservation],
    right: Iterable[GenotypeObservation],
) -> IbsComparison:
    """Compare compatible selected diploid calls without making kinship claims."""

    left_items = tuple(sorted(left, key=lambda item: item.observation_id))
    unmatched_right = list(sorted(right, key=lambda item: item.observation_id))
    ibs_counts = Counter[int]()
    differing = no_calls = incompatible = missing_left = 0

    for left_item in left_items:
        right_index = _matching_index(left_item, unmatched_right)
        if right_index is None:
            missing_left += 1
            continue
        right_item = unmatched_right.pop(right_index)
        if not _compatible(left_item, right_item):
            incompatible += 1
            continue
        if left_item.no_call or right_item.no_call:
            no_calls += 1
            continue
        shared = sum((Counter(left_item.normalized_genotype or "") & Counter(right_item.normalized_genotype or "")).values())
        ibs_counts[shared] += 1
        differing += left_item.normalized_genotype != right_item.normalized_genotype

    missing = missing_left + len(unmatched_right)
    common = sum(ibs_counts.values())
    insufficient = common == 0
    similarity = None if insufficient else (ibs_counts[2] + 0.5 * ibs_counts[1]) / common
    limitations = [
        "IBS over selected consumer loci cannot establish legal, forensic, or biological kinship."
    ]
    if insufficient:
        limitations.append("No compatible called loci were available; no similarity is reported.")
    if no_calls or missing or incompatible:
        limitations.append("No-call, missing, or build/orientation-incompatible loci were excluded.")
    return IbsComparison(
        common_loci=common,
        differing_genotypes=differing,
        ibs0=ibs_counts[0],
        ibs1=ibs_counts[1],
        ibs2=ibs_counts[2],
        no_call_loci=no_calls,
        missing_loci=missing,
        incompatible_loci=incompatible,
        similarity=similarity,
        insufficient_coverage=insufficient,
        limitations=tuple(limitations),
    )


def _matching_index(
    left: GenotypeObservation,
    right_items: list[GenotypeObservation],
) -> int | None:
    if left.rsid:
        for index, right in enumerate(right_items):
            if right.rsid == left.rsid:
                return index
    for index, right in enumerate(right_items):
        if right.chromosome == left.chromosome and right.position == left.position:
            return index
    return None


def _compatible(left: GenotypeObservation, right: GenotypeObservation) -> bool:
    return (
        left.genome_build is right.genome_build
        and left.genome_build is not GenomeBuild.UNKNOWN
        and left.orientation is OrientationState.RESOLVED
        and right.orientation is OrientationState.RESOLVED
    )
