"""Stable public surface for the portable trust package (Sentient G4).

This module is the canonical, curated public API for the generic trust layer
previously proven in G1/G2/G3. G4 does not introduce a new security model: the
contracts, canonicalization, hashing, builders, and validators re-exported here
are the same objects the OpenCare runtime already uses.

Stable for G4 (import these from ``app.agent_trust.api``):

- Contract models: ``TrustEnvelope``, ``ExecutionReceipt``, ``AuthorizationSnapshot``,
  ``AuthorizationDecision``, ``EvidenceItem``, ``ProviderDisclosure``,
  ``SafetyDecision``, ``FinalDecision``.
- Trusted builder: ``TrustedEnvelopeBuilder``, ``EnvelopeRequest``, ``BuildRefused``.
- Canonical helpers: ``canonical_bytes``, ``envelope_id``, ``receipt_id``,
  ``receipt_sha256``, ``strict_json_loads``, ``sha256_hex``.
- Validators: ``validate_envelope_bytes``, ``validate_receipt_bytes`` (and their
  ``ValidationResult`` return type).
- The generic authorization boundary: ``AuthorizationAdapter`` (a Protocol).
- Controlled identifiers/constants: ``PurposeId``, ``ActionId``, ``ToolId``,
  ``PURPOSE_IDS``, ``ACTION_REQUIREMENTS``, ``TOOL_IDS``,
  ``PROHIBITED_OPERATIONS``, ``DEFAULT_DISCLOSURE_CONSTRAINTS``.

Implementation details (import only when you know you need them, never from a
portable consumer):

- ``app.agent_trust.builders`` internals (including the broader ``TrustAuthority``
  extension protocol and ``build_execution_receipt``);
- ``app.agent_trust.models`` / ``canonical`` / ``validation`` / ``identifiers`` /
  ``authorization`` / ``schemas`` / ``fixtures`` / ``testing`` submodules;
- ``app.agent_trust.cli`` (the ``opencare-trust`` command line).

This module intentionally exposes NO Product Core repositories, live database
handles, ``FamilyAccessService``, FastAPI objects, session stores, or health
repositories. The OpenCare-specific adapter lives in ``app.agent.trust_adapter``
and implements the generic ``AuthorizationAdapter`` protocol.
"""

from __future__ import annotations

from app.agent_trust.authorization import AuthorizationAdapter
from app.agent_trust.builders import BuildRefused, EnvelopeRequest, TrustedEnvelopeBuilder
from app.agent_trust.canonical import (
    canonical_bytes,
    envelope_id,
    receipt_id,
    receipt_sha256,
    sha256_hex,
    strict_json_loads,
)
from app.agent_trust.identifiers import (
    ACTION_REQUIREMENTS,
    DEFAULT_DISCLOSURE_CONSTRAINTS,
    PROHIBITED_OPERATIONS,
    PURPOSE_IDS,
    TOOL_IDS,
    ActionId,
    PurposeId,
    ToolId,
)
from app.agent_trust.models import (
    AuthorizationDecision,
    AuthorizationSnapshot,
    EvidenceItem,
    ExecutionReceipt,
    FinalDecision,
    ProviderDisclosure,
    SafetyDecision,
    TrustEnvelope,
)
from app.agent_trust.validation import (
    ValidationResult,
    validate_envelope_bytes,
    validate_receipt_bytes,
)

__all__ = [
    # Contract models.
    "TrustEnvelope",
    "ExecutionReceipt",
    "AuthorizationSnapshot",
    "AuthorizationDecision",
    "EvidenceItem",
    "ProviderDisclosure",
    "SafetyDecision",
    "FinalDecision",
    # Trusted builder.
    "TrustedEnvelopeBuilder",
    "EnvelopeRequest",
    "BuildRefused",
    # Canonical helpers.
    "canonical_bytes",
    "envelope_id",
    "receipt_id",
    "receipt_sha256",
    "strict_json_loads",
    "sha256_hex",
    # Validators.
    "validate_envelope_bytes",
    "validate_receipt_bytes",
    "ValidationResult",
    # Generic authorization boundary.
    "AuthorizationAdapter",
    # Controlled identifiers and constants.
    "PurposeId",
    "ActionId",
    "ToolId",
    "PURPOSE_IDS",
    "ACTION_REQUIREMENTS",
    "TOOL_IDS",
    "PROHIBITED_OPERATIONS",
    "DEFAULT_DISCLOSURE_CONSTRAINTS",
]
