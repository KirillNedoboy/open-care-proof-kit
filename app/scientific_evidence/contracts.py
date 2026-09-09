"""Connector-agnostic contracts for external scientific evidence sources.

Pure typed layer: no Product Core, Family Access, FastAPI, storage, or
network imports are permitted anywhere in this package.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, Protocol, TypedDict, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

# UCSC-style primary contigs; AlphaGenome documents human coordinates on the
# hg38/GRCh38 assembly with "chr"-prefixed contig names (e.g. "chr22").
# Server acceptance of un-prefixed names is undocumented, so the external
# projection always requires and emits chr-prefixed contigs.
# chrM, unplaced, and alt contigs are deliberately excluded: every official
# AlphaGenome/Atlas example, doc, and AVI field definition demonstrates only
# chr1-22/X/Y, and no documentation shows mtDNA or alt-contig support, so
# the connector fails closed on anything outside the primary autosomes and
# sex chromosomes rather than guessing at undocumented behavior.
_ALLOWED_CHROMOSOMES = frozenset(
    [f"chr{index}" for index in range(1, 23)] + ["chrX", "chrY"]
)
_BASE_PATTERN = re.compile(r"[ACGT]")


class FrozenModel(BaseModel):
    """Immutable, closed model; matches the app.genetics domain convention."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceKind(StrEnum):
    """What class of system a connector talks to."""

    EXTERNAL_SCIENTIFIC_EVIDENCE = "external_scientific_evidence"


class CommercialUseClass(StrEnum):
    """Commercial-use posture taken from the official AlphaGenome terms.

    As checked 2026-09-09, the AlphaGenome Services Additional Terms carve
    out the standalone AVI Score for commercial use, while the AVI Score
    Feature Breakdown and other outputs remain non-commercial only; the
    full model is separately available for commercial use via Google Cloud.
    """

    NOT_PERMITTED = "not_permitted"
    PARTIAL_AVI_SCORE_ONLY = "partial_avi_score_only"
    PERMITTED_ONLY_VIA_GOOGLE_CLOUD = "permitted_only_via_google_cloud"


class AtlasGenomeBuild(StrEnum):
    """The only assembly the AlphaGenome Atlas documents for human scores.

    Official documentation states human predictions use hg38 (GRCh38.p13)
    with GENCODE v46 annotation and directs users to external lift-over
    tooling for other builds. This connector therefore supports exactly
    GRCh38 and fails closed on anything else; it never performs liftover.
    """

    GRCH38 = "GRCh38"


class UnsupportedGenomeBuildError(TypeError):
    """Raised when a caller asks for an assembly this connector cannot use.

    ``reason`` is a stable machine-readable code; no conversion is ever
    attempted for unknown or incompatible builds. Deliberately subclasses
    ``TypeError`` (not ``ValueError``): pydantic v2 wraps ``ValueError``
    raised inside validators into ``ValidationError`` but propagates any
    other exception type unchanged, which keeps this typed error — and its
    stable reason — reachable from model validation.
    """

    reason = "unsupported_genome_build"


class UsagePolicy(FrozenModel):
    """Typed usage constants carried alongside evidence.

    This is deliberately not an enforcement engine. Downstream code must
    consciously bypass these typed distinctions to misrepresent research
    evidence as clinical guidance.
    """

    usage_class: Literal["research_only"] = "research_only"
    clinical_decision_support: Literal[False] = False
    medical_advice: Literal[False] = False
    diagnosis: Literal[False] = False
    prognosis: Literal[False] = False
    outputs_for_ml_training: Literal[False] = False


DEFAULT_RESEARCH_ONLY_USAGE_POLICY = UsagePolicy()


class ConnectorDescriptor(FrozenModel):
    """Immutable, secret-free identity and usage metadata for a connector."""

    connector_id: str = Field(min_length=1, max_length=120)
    source_name: str = Field(min_length=1, max_length=120)
    source_kind: SourceKind
    external: Literal[True] = True
    requires_api_key: Literal[True] = True
    research_only: Literal[True] = True
    clinical_use_allowed: Literal[False] = False
    commercial_use_class: CommercialUseClass
    terms_reference: str = Field(min_length=1, max_length=500)
    commercial_use_notes: str | None = Field(default=None, max_length=2000)
    reference_assembly: AtlasGenomeBuild | None = None
    gene_annotation_release: str | None = Field(default=None, max_length=80)
    api_version: str | None = Field(default=None, max_length=80)


class TransportVariantRequest(TypedDict):
    """Minimized payload the external transport is allowed to receive.

    Exactly one selected normalized SNV coordinate and the documented
    assembly. Nothing else may be transmitted through a scientific evidence
    connector.
    """

    variant: str
    assembly: str


class SelectedVariantQuery(FrozenModel):
    """Exactly one selected, normalized SNV safe to project outward.

    Structurally impossible to carry raw genotype bytes, VCF payloads,
    sequences, file paths, person identity, or evidence arrays: the model is
    closed (``extra="forbid"``) and every field is a bounded scalar.
    ``provenance_reference`` is an optional opaque internal token and is
    never required by the external transport. Alleles are forward-strand
    reference bases; the Atlas server does not validate REF against the
    genome, so this OpenCare-side validation is authoritative.
    """

    genome_build: AtlasGenomeBuild
    chromosome: str
    position: int = Field(gt=0)
    reference: str
    alternate: str
    provenance_reference: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("genome_build", mode="before")
    @classmethod
    def reject_unknown_build(cls, value: object) -> object:
        """Fail closed with a stable typed reason on any non-documented build."""

        if isinstance(value, str) and value.upper() != AtlasGenomeBuild.GRCH38.upper():
            raise UnsupportedGenomeBuildError(
                "only the documented GRCh38 assembly is supported; no liftover"
            )
        return value

    @field_validator("chromosome")
    @classmethod
    def validate_chromosome(cls, value: str) -> str:
        if value not in _ALLOWED_CHROMOSOMES:
            raise ValueError("invalid_chromosome")
        return value

    @field_validator("reference", "alternate")
    @classmethod
    def validate_single_base(cls, value: str) -> str:
        if len(value) != 1 or not _BASE_PATTERN.fullmatch(value):
            raise ValueError("invalid_base")
        return value

    def model_post_init(self, _context: object) -> None:
        if self.reference == self.alternate:
            raise ValueError("reference_equals_alternate")

    @property
    def variant_string(self) -> str:
        """Documented Atlas variant coordinate form ``chr:pos:ref>alt`` (1-based)."""

        return f"{self.chromosome}:{self.position}:{self.reference}>{self.alternate}"

    def to_transport_request(self) -> TransportVariantRequest:
        """Minimized payload for the external transport; identity-free."""

        return {"variant": self.variant_string, "assembly": self.genome_build.value}


ResultT = TypeVar("ResultT", covariant=True)


@runtime_checkable
class ScientificEvidenceConnector(Protocol[ResultT]):
    """Minimal reusable contract for future sources (e.g. ClinVar, gnomAD).

    One descriptor plus one selected-variant query. Implementations must be
    pure with respect to OpenCare storage: they transform an explicit,
    minimized query into a validated evidence object and nothing more.
    """

    @property
    def descriptor(self) -> ConnectorDescriptor: ...

    def query_variant(self, request: SelectedVariantQuery) -> ResultT: ...
