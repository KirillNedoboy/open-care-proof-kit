"""Validated value objects for the pure genetics research domain."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GenomeBuild(StrEnum):
    """Genome coordinate systems accepted without implicit liftover."""

    GRCH37 = "GRCh37"
    GRCH38 = "GRCh38"
    UNKNOWN = "unknown"


class OrientationState(StrEnum):
    """Whether reported alleles can be compared to an evidence condition."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"


class CoverageState(StrEnum):
    """Deterministic outcome for an evidence target in a dataset."""

    TARGET = "target"
    PRESENT = "present"
    NO_CALL = "no_call"
    NOT_PRESENT = "not_present"
    BUILD_INCOMPATIBLE = "build_incompatible"
    UNRESOLVED = "unresolved"


class EvidenceLevel(StrEnum):
    CLINICAL = "Clinical"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    EXPLORATORY = "Exploratory"
    CONFLICTING = "Conflicting"


class EvidenceCategory(StrEnum):
    PGX = "pgx"
    HEALTH_ASSOCIATION = "health_association"
    CARRIER = "carrier"
    TRAIT = "trait"
    NEURO = "neuro"
    METABOLISM = "metabolism"
    CARDIOVASCULAR = "cardiovascular"
    NUTRITION = "nutrition"
    SLEEP = "sleep"
    EXERCISE = "exercise"
    EXPLORATORY = "exploratory"


class EpistemicStatus(StrEnum):
    """Required user-facing status of every research claim."""

    OBSERVED = "observed"
    SUPPORTED = "supported"
    PLAUSIBLE = "plausible"
    SPECULATIVE = "speculative"
    UNSUPPORTED_OR_CONFLICTING = "unsupported/conflicting"


class ResearchMode(StrEnum):
    EVIDENCE = "evidence"
    EXPLORE = "explore"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GenotypeObservation(FrozenModel):
    """One normalized, selectively retained consumer-genotype observation."""

    observation_id: str = Field(min_length=1)
    rsid: str | None = None
    chromosome: str = Field(min_length=1)
    position: int = Field(gt=0)
    reported_genotype: str
    normalized_genotype: str | None = None
    no_call: bool = False
    genome_build: GenomeBuild
    orientation: OrientationState
    source_locator: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_call_state(self) -> GenotypeObservation:
        if self.no_call != (self.normalized_genotype is None):
            raise ValueError("no-call observations must have no normalized genotype")
        return self


class ConsumerGenotypeImport(FrozenModel):
    """Bounded import result; it deliberately has no raw-content field."""

    genome_build: GenomeBuild
    parsed_locus_count: int = Field(ge=0)
    observations: tuple[GenotypeObservation, ...]

    @property
    def indexed_locus_count(self) -> int:
        return len(self.observations)


class EvidenceEntry(FrozenModel):
    """One citation-bearing deterministic evidence condition."""

    evidence_id: str = Field(min_length=1)
    rsid: str | None = None
    chromosome: str | None = None
    position: int | None = Field(default=None, gt=0)
    gene: str = Field(min_length=1)
    genome_build: GenomeBuild
    matching_genotypes: tuple[str, ...] = Field(min_length=1)
    category: EvidenceCategory
    title: str = Field(min_length=1)
    association: str = Field(min_length=1)
    effect_direction: str | None = None
    evidence_level: EvidenceLevel
    source_name: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    source_url: str | None = None
    source_version_date: str = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    orientation_required: OrientationState = OrientationState.RESOLVED
    safe_rsid_match: bool = False
    tags: tuple[str, ...] = ()
    medication_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_locator(self) -> EvidenceEntry:
        if not self.citation.strip():
            raise ValueError("evidence requires a source citation or reference")
        if any(
            len(genotype) != 2
            or genotype != "".join(sorted(genotype))
            or any(allele not in "ACGT" for allele in genotype)
            for genotype in self.matching_genotypes
        ):
            raise ValueError("matching genotypes must be normalized diploid A/C/G/T calls")
        if self.rsid is None and (self.chromosome is None or self.position is None):
            raise ValueError("evidence requires an rsID or coordinate")
        if self.safe_rsid_match and self.rsid is None:
            raise ValueError("safe rsID matching requires an rsID")
        if self.category is not EvidenceCategory.PGX and self.medication_names:
            raise ValueError("medication names are limited to PGx evidence")
        return self


class GeneticsEvidencePack(FrozenModel):
    pack_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    synthetic_only: bool
    entries: tuple[EvidenceEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pack(self) -> GeneticsEvidencePack:
        if not self.synthetic_only:
            raise ValueError("only synthetic genetics evidence packs are supported")
        ids = [entry.evidence_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique")
        return self


class CandidateFinding(FrozenModel):
    """A deterministic candidate association, never a diagnosis or instruction."""

    finding_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    gene: str = Field(min_length=1)
    normalized_genotype: str = Field(min_length=1)
    category: EvidenceCategory
    evidence_level: EvidenceLevel
    association: str = Field(min_length=1)
    limitations: tuple[str, ...]


class EvidenceAssessment(FrozenModel):
    evidence_id: str
    observation_id: str | None = None
    coverage: CoverageState
    finding: CandidateFinding | None = None


class CoverageReport(FrozenModel):
    target: int = Field(ge=0)
    present: int = Field(ge=0)
    no_call: int = Field(ge=0)
    not_present: int = Field(ge=0)
    build_incompatible: int = Field(ge=0)
    unresolved: int = Field(ge=0)


class PgxMedicationIntersection(FrozenModel):
    finding_id: str
    evidence_id: str
    gene: str
    medication_name: str
    association: str
    evidence_level: EvidenceLevel
    source_name: str
    citation: str
    limitations: tuple[str, ...]


class SelectedHealthRecord(FrozenModel):
    record_id: str
    kind: str = Field(min_length=1)
    data: dict[str, Any]
