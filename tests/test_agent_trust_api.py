"""Stable public API surface for the portable trust package (Sentient G4)."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agent_trust import (
    ACTION_REQUIREMENTS,
    DEFAULT_DISCLOSURE_CONSTRAINTS,
    PROHIBITED_OPERATIONS,
    PURPOSE_IDS,
    TOOL_IDS,
    EnvelopeRequest,
    ExecutionReceipt,
    TrustedEnvelopeBuilder,
    TrustEnvelope,
    ValidationResult,
    api,
    canonical_bytes,
    envelope_id,
    receipt_id,
    receipt_sha256,
    sha256_hex,
    strict_json_loads,
    validate_envelope_bytes,
    validate_receipt_bytes,
)
from app.agent_trust import api as api_module
from app.agent_trust.testing import SyntheticAuthority

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2027, 8, 2, 10, 0, tzinfo=UTC)

STABLE_EXPORTS = (
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
)


def test_stable_exports_are_listed_in_api_all() -> None:
    assert set(STABLE_EXPORTS) == set(api_module.__all__)
    for name in STABLE_EXPORTS:
        assert hasattr(api_module, name)


def test_stable_exports_are_reexported_from_package() -> None:
    package = importlib.import_module("app.agent_trust")
    for name in STABLE_EXPORTS:
        assert hasattr(package, name)
    assert package.__all__ == api_module.__all__


def test_stable_exports_are_identical_objects_to_their_source_modules() -> None:
    from app.agent_trust import builders as builders_module
    from app.agent_trust import canonical as canonical_module
    from app.agent_trust import models as models_module
    from app.agent_trust import validation as validation_module

    assert api.TrustEnvelope is models_module.TrustEnvelope
    assert api.ExecutionReceipt is models_module.ExecutionReceipt
    assert api.TrustedEnvelopeBuilder is builders_module.TrustedEnvelopeBuilder
    assert api.canonical_bytes is canonical_module.canonical_bytes
    assert api.validate_envelope_bytes is validation_module.validate_envelope_bytes


def test_builder_validators_and_canonicalization_work_through_api() -> None:
    request = EnvelopeRequest(
        actor_id="actor-alice",
        credential_id="credential-alice",
        person_id="person-alice",
        purpose_id="visit_preparation",
        action_id="summarize_records",
        requested_action="Summarize selected records for visit preparation.",
        requested_tools=["context.read", "source.read"],
        evidence_ids=["evidence-medication-alice"],
        disclosure_mode="local_only",
        provider_id=None,
        consent_basis_id="consent-alice",
        ttl_seconds=300,
    )
    envelope = TrustedEnvelopeBuilder(
        SyntheticAuthority.allowed(now=NOW), clock=lambda: NOW
    ).build(request)
    payload = canonical_bytes(envelope) + b"\n"
    result = validate_envelope_bytes(payload, at=NOW)
    assert isinstance(result, ValidationResult)
    assert result.valid
    assert envelope.envelope_id == envelope_id(envelope)
    assert envelope.envelope_id.startswith("sha256:")
    assert len(sha256_hex(canonical_bytes(envelope))) == 64

    receipt = _build_receipt(envelope)
    receipt_payload = canonical_bytes(receipt) + b"\n"
    receipt_result = validate_receipt_bytes(receipt_payload, envelope=envelope, at=NOW)
    assert receipt_result.valid
    assert receipt.receipt_id == receipt_id(receipt)
    assert len(receipt_sha256(receipt)) == 64
    assert receipt.envelope_id == envelope.envelope_id


def _build_receipt(envelope: TrustEnvelope) -> ExecutionReceipt:
    from app.agent_trust.builders import build_execution_receipt

    return build_execution_receipt(
        envelope=envelope,
        started_at=NOW + timedelta(seconds=1),
        completed_at=NOW + timedelta(seconds=2),
        status="completed",
        provider_id=None,
        used_evidence_ids=["evidence-medication-alice"],
        used_tools=["context.read"],
        output=b"safe output",
        reason_codes=[],
    )


def test_strict_json_loads_rejects_non_canonical_input() -> None:
    envelope = TrustedEnvelopeBuilder(
        SyntheticAuthority.allowed(now=NOW), clock=lambda: NOW
    ).build(
        EnvelopeRequest(
            actor_id="actor-alice",
            credential_id="credential-alice",
            person_id="person-alice",
            purpose_id="visit_preparation",
            action_id="summarize_records",
            requested_action="Summarize selected records.",
            requested_tools=["context.read", "source.read"],
            evidence_ids=["evidence-medication-alice"],
            disclosure_mode="local_only",
            provider_id=None,
            consent_basis_id="consent-alice",
            ttl_seconds=300,
        )
    )
    payload = canonical_bytes(envelope)
    assert strict_json_loads(payload)["person_id"] == "person-alice"
    with pytest.raises(ValueError):
        strict_json_loads(b"\xef\xbb\xbf" + payload)
    with pytest.raises(ValueError):
        strict_json_loads(payload + b"\r")
    with pytest.raises(ValueError):
        strict_json_loads(b'{"a":1,"a":2}')


def test_controlled_identifier_constants_are_stable() -> None:
    assert frozenset(
        {"visit_preparation", "record_explanation", "clinician_briefing"}
    ) == PURPOSE_IDS
    assert frozenset({"context.read", "source.read", "brief.draft"}) == TOOL_IDS
    assert "answer_question" in ACTION_REQUIREMENTS
    assert "diagnosis" in PROHIBITED_OPERATIONS
    assert "disclose_only_selected_fields" in DEFAULT_DISCLOSURE_CONSTRAINTS


def test_reference_example_imports_and_runs_cleanly() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "portable-trust" / "reference_example.py"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["synthetic_offline_fixture_only"] is True
    assert payload["not_live_authorization"] is True
    assert payload["envelope_valid"] is True
    assert payload["receipt_valid"] is True


def test_api_does_not_expose_runtime_objects() -> None:
    exposed = {
        name for name in dir(api_module) if not name.startswith("_")
    }
    assert "FamilyAccessService" not in exposed
    assert "SQLiteDatabase" not in exposed
    assert "SessionStore" not in exposed
    assert "ProductCoreRuntime" not in exposed
    assert "FastAPI" not in exposed
