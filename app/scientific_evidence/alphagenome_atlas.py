"""AlphaGenome Atlas scientific evidence connector (domain layer).

OpenCare-owned types implemented from the public, documented semantics of
the AlphaGenome Atlas API only (official repository README/docs and the
AlphaGenome Services Additional Terms; sources accessed 2026-09-09). This
module deliberately contains no network transport, no credentials, and no
Product Core imports.

Official API facts reflected here (transport itself is deferred):
    Client factory ``alphagenome.atlas.atlas.create(api_key)``; single
    variant queries via ``query_variant(variant, requested_scorers=
    ['AVI_SCORE', 'AVI_SCORE_FEATURE_IMPORTANCE'])``; the documented variant
    string form is ``chr:pos:ref>alt`` with 1-based positions, chr-prefixed
    chromosomes, and forward-strand alleles on hg38 (GRCh38.p13) with
    GENCODE v46 annotation. The server does not validate REF against the
    genome, so OpenCare-side validation is authoritative.

AVI semantics — load-bearing contract:
    The AlphaGenome Variant Impact (AVI) score is a *predicted molecular /
    functional impact* measure. It is NOT pathogenicity truth, NOT disease
    probability, NOT penetrance, NOT a diagnosis, NOT prognosis, and NOT a
    clinical risk score. The official research-use rules forbid
    extrapolating high functional impact to clinical disease causation.
    Consequently no ClinVar-style classification field (Pathogenic, Likely
    Pathogenic, Benign, VUS) exists anywhere on these result types, and none
    may be added downstream of this module without a deliberate review.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from app.scientific_evidence.contracts import (
    DEFAULT_RESEARCH_ONLY_USAGE_POLICY,
    AtlasGenomeBuild,
    CommercialUseClass,
    ConnectorDescriptor,
    FrozenModel,
    SelectedVariantQuery,
    SourceKind,
    TransportVariantRequest,
    UsagePolicy,
)

# Official documented Atlas variant scorer names (science-skills AVI
# analysis, "Output Schemas & Response Structures", accessed 2026-09-09).
AVI_SCORE = "AVI_SCORE"
AVI_SCORE_FEATURE_IMPORTANCE = "AVI_SCORE_FEATURE_IMPORTANCE"

# The exactly-18 documented biological feature attribution modalities
# (official AVI analysis metadata; join by name, never positionally).
DOCUMENTED_FEATURE_MODALITIES = frozenset(
    {
        "MERGED_SPLICING",
        "MAX_ABS_RNA_SEQ",
        "MAX_ABS_ATAC",
        "MAX_ABS_DNASE",
        "MAX_ABS_CHIP_TF",
        "MAX_ABS_CHIP_HISTONE",
        "MAX_ABS_CAGE",
        "MAX_ABS_PROCAP",
        "MAX_ABS_POLYADENYLATION",
        "MAX_ABS_CONTACT_MAPS",
        "ALPHAMISSENSE",
        "CACTUS_241_WAY",
        "PROTEIN_TERMINATION",
        "START_LOST",
        "STOP_LOST",
        "PHASTCONS_470_WAY",
        "IS_INSERTION",
        "IS_DELETION",
    }
)

# Official documented record identity: ``chr:pos_1_based:ref>alt``.
# chr1-22/X/Y only: no official AlphaGenome documentation demonstrates chrM
# support, so the connector fails closed on anything outside that set.
_VARIANT_FIELD_PATTERN = re.compile(
    r"^chr([1-9]|1[0-9]|2[0-2]|X|Y):([1-9]\d*):([ACGT])>([ACGT])$"
)

# Bounds derived from the official subfield definitions:
#   AVI_PHRED calibrated range [0.0, ~70.0] (70 is a derived bound implied
#   by the documented 1e-7 quantile tail floor); AVI_QUANTILE tail quantile
#   (1 - CDF) range (0.0, 1.0]; top percentile is a percentage in (0.0, 100.0].
_PHRED_MAX = 70.0
_MAX_FEATURE_ATTRIBUTIONS = 18
_MAX_SCORERS = 4


class AlphaGenomeEvidenceValidationError(ValueError):
    """Fail-closed reason for any malformed or mismatched Atlas response.

    ``reason`` is a stable machine-readable code; the message is operator
    text only and never carries raw response payloads.
    """

    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


class ScoreSemantics(FrozenModel):
    """Typed metadata pinning what an AVI score does and does not mean."""

    measures: Literal["predicted_molecular_functional_impact"] = (
        "predicted_molecular_functional_impact"
    )
    is_pathogenicity_truth: Literal[False] = False
    is_disease_probability: Literal[False] = False
    is_penetrance_estimate: Literal[False] = False
    is_diagnosis: Literal[False] = False
    is_prognosis: Literal[False] = False
    is_clinical_risk_score: Literal[False] = False


class FeatureAttribution(FrozenModel):
    """One documented per-modality attribution weight (SHAP value)."""

    modality: str = Field(min_length=1, max_length=80)
    importance: float


class AlphaGenomeEvidenceResult(FrozenModel):
    """Bounded, normalized AlphaGenome Atlas evidence for one SNV.

    Contains only the officially documented summary fields for a queried
    variant: the echoed variant, the AVI score set, the top modality and
    attribution, bounded feature-attribution weights, source identity and
    assembly/annotation provenance, retrieval time, and preserved
    provenance reference. Calibrated fields (``avi_phred``,
    ``avi_quantile``, ``top_percentile``) are typed-optional ``None`` when
    the Atlas response carries no calibrated quantile layer — they are
    never fabricated as zero. There is deliberately no track catalog,
    tensor, plot, HTTP metadata, credential, ClinVar-style classification,
    or clinical interpretation field.
    """

    # Echoed query identity (validated to match the request exactly).
    chromosome: str
    position: int = Field(gt=0)
    reference: str
    alternate: str
    variant: str

    # Officially documented AVI score fields.
    avi_raw: float
    avi_phred: float | None = Field(default=None, ge=0.0, le=_PHRED_MAX)
    avi_quantile: float | None = Field(default=None, gt=0.0, le=1.0)
    top_percentile: float | None = Field(default=None, gt=0.0, le=100.0)
    top_modality: str | None = Field(default=None, min_length=1, max_length=80)
    top_feature_importance: float | None = None

    # Optional bounded per-modality attribution weights (18 documented).
    feature_attributions: tuple[FeatureAttribution, ...] = ()

    # Source identity and provenance.
    connector_id: Literal["opencare.alphagenome_atlas"] = "opencare.alphagenome_atlas"
    source_name: Literal["AlphaGenome Atlas"] = "AlphaGenome Atlas"
    genome_build: AtlasGenomeBuild
    reference_assembly: Literal["hg38 (GRCh38.p13)"] = "hg38 (GRCh38.p13)"
    gene_annotation_release: Literal["GENCODE v46"] = "GENCODE v46"
    requested_scorers: tuple[str, ...] = (AVI_SCORE,)
    terms_reference: Literal[
        "https://deepmind.google.com/science/alphagenome/terms"
    ] = "https://deepmind.google.com/science/alphagenome/terms"
    retrieved_at: datetime
    response_schema_version: str = Field(min_length=1, max_length=80)
    provenance_reference: str | None = Field(default=None, min_length=1, max_length=200)

    # Typed semantics + usage boundary.
    score_semantics: ScoreSemantics = ScoreSemantics()
    usage_policy: UsagePolicy = DEFAULT_RESEARCH_ONLY_USAGE_POLICY

    @model_validator(mode="after")
    def validate_identity_echo(self) -> AlphaGenomeEvidenceResult:
        """The echoed variant must parse and equal its own components."""

        match = _VARIANT_FIELD_PATTERN.fullmatch(self.variant)
        if match is None:
            raise AlphaGenomeEvidenceValidationError("malformed_variant_identity")
        chrom, pos, ref, alt = match.groups()
        if (
            chrom != self.chromosome.removeprefix("chr")
            or int(pos) != self.position
            or ref != self.reference
            or alt != self.alternate
        ):
            raise AlphaGenomeEvidenceValidationError("variant_identity_inconsistent")
        return self

    @model_validator(mode="after")
    def validate_calibrated_coherence(self) -> AlphaGenomeEvidenceResult:
        """Percentile is only meaningful together with its quantile layer."""

        calibrated = (self.avi_phred, self.avi_quantile)
        if any(value is not None for value in calibrated) and None in calibrated:
            raise AlphaGenomeEvidenceValidationError("partial_quantile_layer")
        return self

    @field_validator(
        "avi_raw", "avi_phred", "avi_quantile", "top_percentile", "top_feature_importance"
    )
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise AlphaGenomeEvidenceValidationError("non_finite_score")
        return value

    @field_validator("requested_scorers")
    @classmethod
    def validate_scorers_bounded(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > _MAX_SCORERS or any(
            not scorer or len(scorer) > 80 for scorer in value
        ):
            raise AlphaGenomeEvidenceValidationError("scorer_collection_overflow")
        return value


class AlphaGenomeTransport(Protocol):
    """Network transport contract, isolated from domain parsing.

    A transport turns the minimized, identity-free request payload into a
    raw response mapping of documented field names to values. The
    production transport (official SDK/gRPC, ``x-goog-api-key`` auth via
    ``atlas.create(api_key)``) is intentionally NOT implemented at this
    stage; tests inject a deterministic fake. Implementations must never
    receive anything beyond ``SelectedVariantQuery.to_transport_request()``
    and must never surface credentials or HTTP metadata upward.
    """

    def fetch_variant_scores(
        self, payload: TransportVariantRequest
    ) -> dict[str, Any]: ...


def _optional_finite_float(response: dict[str, Any], key: str) -> float | None:
    if key not in response or response[key] is None:
        return None
    value = response[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AlphaGenomeEvidenceValidationError(f"malformed_{key}")
    if not math.isfinite(float(value)):
        raise AlphaGenomeEvidenceValidationError(f"non_finite_{key}")
    return float(value)


def _require_finite_float(response: dict[str, Any], key: str) -> float:
    value = _optional_finite_float(response, key)
    if value is None:
        raise AlphaGenomeEvidenceValidationError(f"missing_{key}")
    return value


def normalize_atlas_response(
    response: dict[str, Any],
    *,
    request: SelectedVariantQuery,
    retrieved_at: datetime,
    response_schema_version: str,
) -> AlphaGenomeEvidenceResult:
    """Strictly normalize one documented Atlas record for one query.

    Fails closed — never heuristically recovers — on: missing AVI_SCORE
    score identity (``avi_raw``) or empty scores, malformed variant
    identity, queried-versus-result mismatch, unexpected assembly,
    non-finite or malformed numerics, unknown/oversized attribution keys,
    and any unbounded collection. Absent calibrated fields (no quantile
    layer) are preserved as typed ``None``, never fabricated. The input
    must be a flat mapping of the documented field names (``variant``,
    ``avi_raw``, ``avi_phred``, ``avi_quantile``, ``top_percentile``,
    ``top_modality``, ``top_feature_importance``, optional ``fi_<MODALITY>``
    attribution weights, optional ``schema_version``).
    """

    if not isinstance(response, dict) or not response:
        raise AlphaGenomeEvidenceValidationError("malformed_or_empty_response")

    variant = response.get("variant")
    if not isinstance(variant, str):
        raise AlphaGenomeEvidenceValidationError("missing_variant_identity")
    match = _VARIANT_FIELD_PATTERN.fullmatch(variant)
    if match is None:
        raise AlphaGenomeEvidenceValidationError("malformed_variant_identity")
    chrom, pos, ref, alt = match.groups()
    if (
        f"chr{chrom}" != request.chromosome
        or int(pos) != request.position
        or ref != request.reference
        or alt != request.alternate
    ):
        raise AlphaGenomeEvidenceValidationError("queried_result_variant_mismatch")

    assembly = response.get("assembly")
    if assembly is not None and assembly != AtlasGenomeBuild.GRCH38.value:
        raise AlphaGenomeEvidenceValidationError("unexpected_genome_build")

    # AVI_SCORE identity: the raw score is the scorer itself; no scores at
    # all means no evidence object.
    avi_raw = _require_finite_float(response, "avi_raw")
    avi_phred = _optional_finite_float(response, "avi_phred")
    avi_quantile = _optional_finite_float(response, "avi_quantile")
    top_percentile = _optional_finite_float(response, "top_percentile")

    # Feature-breakdown fields belong to AVI_SCORE_FEATURE_IMPORTANCE.
    top_modality = response.get("top_modality")
    if top_modality is not None and (
        not isinstance(top_modality, str) or not top_modality
    ):
        raise AlphaGenomeEvidenceValidationError("malformed_top_modality")
    top_feature_importance = _optional_finite_float(response, "top_feature_importance")

    attributions: list[FeatureAttribution] = []
    for key in sorted(response):
        if not key.startswith("fi_"):
            continue
        if len(attributions) >= _MAX_FEATURE_ATTRIBUTIONS:
            raise AlphaGenomeEvidenceValidationError("attribution_collection_overflow")
        modality = key.removeprefix("fi_")
        if modality not in DOCUMENTED_FEATURE_MODALITIES:
            raise AlphaGenomeEvidenceValidationError("unknown_attribution_modality")
        value = response[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AlphaGenomeEvidenceValidationError("malformed_attribution_value")
        if not math.isfinite(float(value)):
            raise AlphaGenomeEvidenceValidationError("non_finite_attribution_value")
        attributions.append(FeatureAttribution(modality=modality, importance=float(value)))

    # The feature-breakdown scorer is reported only when a per-modality
    # attribution map is actually present; the top-modality summary fields
    # accompany the AVI_SCORE record and must not fabricate the breakdown.
    has_breakdown = bool(attributions)
    scorers = (
        AVI_SCORE,
        AVI_SCORE_FEATURE_IMPORTANCE,
    ) if has_breakdown else (AVI_SCORE,)

    try:
        return AlphaGenomeEvidenceResult(
            chromosome=request.chromosome,
            position=request.position,
            reference=request.reference,
            alternate=request.alternate,
            variant=variant,
            avi_raw=avi_raw,
            avi_phred=avi_phred,
            avi_quantile=avi_quantile,
            top_percentile=top_percentile,
            top_modality=top_modality,
            top_feature_importance=top_feature_importance,
            feature_attributions=tuple(attributions),
            genome_build=request.genome_build,
            requested_scorers=scorers,
            retrieved_at=retrieved_at,
            response_schema_version=response_schema_version,
            provenance_reference=request.provenance_reference,
        )
    except AlphaGenomeEvidenceValidationError:
        raise
    except ValueError as error:
        # Model bound violations (e.g. quantile outside (0, 1], phred > 70).
        raise AlphaGenomeEvidenceValidationError("score_out_of_documented_range") from error


ATLAS_CONNECTOR_DESCRIPTOR = ConnectorDescriptor(
    connector_id="opencare.alphagenome_atlas",
    source_name="AlphaGenome Atlas",
    source_kind=SourceKind.EXTERNAL_SCIENTIFIC_EVIDENCE,
    external=True,
    requires_api_key=True,
    research_only=True,
    clinical_use_allowed=False,
    commercial_use_class=CommercialUseClass.PARTIAL_AVI_SCORE_ONLY,
    terms_reference="https://deepmind.google.com/science/alphagenome/terms",
    reference_assembly=AtlasGenomeBuild.GRCH38,
    gene_annotation_release="GENCODE v46 (assembly hg38 / GRCh38.p13)",
    commercial_use_notes=(
        "Per the AlphaGenome Terms as checked 2026-09-09: the standalone AVI "
        "Score is carved out for commercial use, while the AVI Score Feature "
        "Breakdown and all other outputs are non-commercial only; the full "
        "model is separately available commercially via Google Cloud."
    ),
    api_version=None,
)


class AlphaGenomeAtlasConnector:
    """Scientific evidence connector for the AlphaGenome Atlas AVI scores.

    Composes a transport (network-isolated protocol) with the strict
    normalizer. It performs no storage, no identity resolution, and no
    classification; it converts exactly one selected SNV query into one
    validated evidence result. The production transport is deferred to the
    post-D2.2 integration; wiring a fake transport is test-only.
    """

    def __init__(self, transport: AlphaGenomeTransport) -> None:
        self._transport = transport

    @property
    def descriptor(self) -> ConnectorDescriptor:
        return ATLAS_CONNECTOR_DESCRIPTOR

    def query_variant(self, request: SelectedVariantQuery) -> AlphaGenomeEvidenceResult:
        """Query one selected SNV; never batch, never liftover, never raw data."""

        payload = request.to_transport_request()
        response = self._transport.fetch_variant_scores(payload)
        version = response.get("schema_version")
        schema_version = (
            version[:80]
            if isinstance(version, str) and version
            else "alphagenome-atlas-record-v1"
        )
        return normalize_atlas_response(
            response,
            request=request,
            retrieved_at=datetime.now(UTC),
            response_schema_version=schema_version,
        )
