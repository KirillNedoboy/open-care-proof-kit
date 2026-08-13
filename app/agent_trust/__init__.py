"""Trust-bound agent execution contracts and integrity validation.

``app.agent_trust.api`` is the canonical stable public surface for the portable
trust package (Sentient G4) and is re-exported here for convenience. Everything
else under ``app.agent_trust`` is an implementation detail.
"""

from __future__ import annotations

from app.agent_trust.api import (
    ACTION_REQUIREMENTS,
    DEFAULT_DISCLOSURE_CONSTRAINTS,
    PROHIBITED_OPERATIONS,
    PURPOSE_IDS,
    TOOL_IDS,
    ActionId,
    AuthorizationAdapter,
    AuthorizationDecision,
    AuthorizationSnapshot,
    BuildRefused,
    EnvelopeRequest,
    EvidenceItem,
    ExecutionReceipt,
    FinalDecision,
    ProviderDisclosure,
    PurposeId,
    SafetyDecision,
    ToolId,
    TrustedEnvelopeBuilder,
    TrustEnvelope,
    ValidationResult,
    canonical_bytes,
    envelope_id,
    receipt_id,
    receipt_sha256,
    sha256_hex,
    strict_json_loads,
    validate_envelope_bytes,
    validate_receipt_bytes,
)

__all__ = [
    "TrustEnvelope",
    "ExecutionReceipt",
    "AuthorizationSnapshot",
    "AuthorizationDecision",
    "EvidenceItem",
    "ProviderDisclosure",
    "SafetyDecision",
    "FinalDecision",
    "TrustedEnvelopeBuilder",
    "EnvelopeRequest",
    "BuildRefused",
    "canonical_bytes",
    "envelope_id",
    "receipt_id",
    "receipt_sha256",
    "strict_json_loads",
    "sha256_hex",
    "validate_envelope_bytes",
    "validate_receipt_bytes",
    "ValidationResult",
    "AuthorizationAdapter",
    "PurposeId",
    "ActionId",
    "ToolId",
    "PURPOSE_IDS",
    "ACTION_REQUIREMENTS",
    "TOOL_IDS",
    "PROHIBITED_OPERATIONS",
    "DEFAULT_DISCLOSURE_CONSTRAINTS",
]
