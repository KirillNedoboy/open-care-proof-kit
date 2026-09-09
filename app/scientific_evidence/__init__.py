"""Isolated external scientific evidence connector contracts.

This package is a pure, typed connector layer. It deliberately does not
import Product Core, Family Access, FastAPI, storage, or any network stack;
a future transport and evidence-persistence layer will be built against the
contracts defined here after D2.2.
"""

from app.scientific_evidence.alphagenome_atlas import (
    ATLAS_CONNECTOR_DESCRIPTOR,
    AVI_SCORE,
    AVI_SCORE_FEATURE_IMPORTANCE,
    AlphaGenomeAtlasConnector,
    AlphaGenomeEvidenceResult,
    AlphaGenomeEvidenceValidationError,
    AlphaGenomeTransport,
    ScoreSemantics,
    normalize_atlas_response,
)
from app.scientific_evidence.contracts import (
    DEFAULT_RESEARCH_ONLY_USAGE_POLICY,
    AtlasGenomeBuild,
    CommercialUseClass,
    ConnectorDescriptor,
    ScientificEvidenceConnector,
    SelectedVariantQuery,
    SourceKind,
    UsagePolicy,
)

__all__ = [
    "ATLAS_CONNECTOR_DESCRIPTOR",
    "AVI_SCORE",
    "AVI_SCORE_FEATURE_IMPORTANCE",
    "AlphaGenomeAtlasConnector",
    "AlphaGenomeEvidenceResult",
    "AlphaGenomeEvidenceValidationError",
    "AlphaGenomeTransport",
    "AtlasGenomeBuild",
    "CommercialUseClass",
    "ConnectorDescriptor",
    "DEFAULT_RESEARCH_ONLY_USAGE_POLICY",
    "ScoreSemantics",
    "ScientificEvidenceConnector",
    "SelectedVariantQuery",
    "SourceKind",
    "UsagePolicy",
    "normalize_atlas_response",
]
