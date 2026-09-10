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
from app.scientific_evidence.operator_config import (
    AlphaGenomeConfigurationState,
    AlphaGenomeOperatorConfig,
    AlphaGenomeRuntimeStatus,
    alphagenome_runtime_status_from_settings,
    build_alphagenome_operator_config,
    derive_alphagenome_runtime_status,
)

__all__ = [
    "ATLAS_CONNECTOR_DESCRIPTOR",
    "AVI_SCORE",
    "AVI_SCORE_FEATURE_IMPORTANCE",
    "AlphaGenomeAtlasConnector",
    "AlphaGenomeConfigurationState",
    "AlphaGenomeEvidenceResult",
    "AlphaGenomeEvidenceValidationError",
    "AlphaGenomeOperatorConfig",
    "AlphaGenomeRuntimeStatus",
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
    "alphagenome_runtime_status_from_settings",
    "build_alphagenome_operator_config",
    "derive_alphagenome_runtime_status",
    "normalize_atlas_response",
]
