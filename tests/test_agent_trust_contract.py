from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent_trust.builders import (
    BuildRefused,
    EnvelopeRequest,
    TrustedEnvelopeBuilder,
    build_execution_receipt,
)
from app.agent_trust.canonical import canonical_bytes, envelope_id, sha256_hex
from app.agent_trust.models import EvidenceItem, SafetyDecision
from app.agent_trust.testing import SyntheticAuthority
from app.agent_trust.validation import validate_envelope_bytes, validate_receipt_bytes

NOW = datetime(2027, 8, 2, 10, 0, tzinfo=UTC)


def authority() -> SyntheticAuthority:
    return SyntheticAuthority.allowed(now=NOW)


def request(**changes: object) -> EnvelopeRequest:
    values: dict[str, object] = {
        "actor_id": "actor-alice",
        "credential_id": "credential-alice",
        "person_id": "person-alice",
        "purpose_id": "visit_preparation",
        "action_id": "summarize_records",
        "requested_action": "Summarize selected records for visit preparation.",
        "requested_tools": ["context.read", "source.read"],
        "evidence_ids": ["evidence-medication-alice"],
        "disclosure_mode": "local_only",
        "provider_id": None,
        "consent_basis_id": "consent-alice",
        "ttl_seconds": 300,
    }
    values.update(changes)
    return EnvelopeRequest.model_validate(values)


def build(**changes: object):  # type: ignore[no-untyped-def]
    return TrustedEnvelopeBuilder(authority(), clock=lambda: NOW).build(request(**changes))


def test_allowed_envelope_is_minimal_frozen_and_content_addressed() -> None:
    envelope = build()
    assert envelope.person_id == "person-alice"
    assert envelope.resource_scopes == ["person.read", "source.read"]
    assert envelope.authorization.snapshot is not None
    assert envelope.authorization.snapshot.granted_scopes != envelope.resource_scopes
    assert envelope.envelope_id == envelope_id(envelope)
    assert envelope.provider_disclosure.allowed_evidence_ids == ["evidence-medication-alice"]
    with pytest.raises(ValidationError):
        envelope.person_id = "person-carol"  # type: ignore[misc]


def test_wrong_person_carol_revoked_expired_and_unsupported_requests_refuse() -> None:
    cases = [
        (request(person_id="person-carol"), "person_access_denied"),
        (request(evidence_ids=["evidence-medication-carol"]), "evidence_person_mismatch"),
        (request(actor_id="actor-revoked"), "authorization_revoked"),
        (request(actor_id="actor-expired"), "authorization_expired"),
    ]
    for item, reason in cases:
        with pytest.raises(BuildRefused) as error:
            TrustedEnvelopeBuilder(authority(), clock=lambda: NOW).build(item)
        assert error.value.reason_codes == [reason]
    with pytest.raises(ValidationError):
        request(action_id="delete_records")


def test_missing_provenance_and_mutation_tool_refuse() -> None:
    with pytest.raises(BuildRefused) as missing:
        build(evidence_ids=["evidence-missing-provenance"])
    assert missing.value.reason_codes == ["provenance_missing"]
    with pytest.raises(ValidationError):
        request(requested_tools=["medication.write"])


def test_model_rejects_cross_person_evidence_and_non_utc_times() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="evidence",
            evidence_type="medication_record",
            person_id="person",
            resource_scope="source.read",
            content_sha256="a" * 64,
            source_ids=["source"],
            provenance_status="source_backed",
            selected_fields=["name"],
            observed_at=datetime(2027, 1, 1),
        )


def test_canonical_vector_and_tampering_are_deterministic() -> None:
    envelope = build()
    payload = canonical_bytes(envelope) + b"\n"
    result = validate_envelope_bytes(payload, at=NOW)
    assert result.valid
    assert sha256_hex(canonical_bytes(envelope)) == sha256_hex(canonical_bytes(envelope))

    decoded = json.loads(payload)
    decoded["person_id"] = "person-carol"
    tampered = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    invalid = validate_envelope_bytes(tampered, at=NOW)
    assert not invalid.valid
    assert (
        "envelope_id_mismatch" in invalid.reason_codes or "invalid_contract" in invalid.reason_codes
    )

    assert not validate_envelope_bytes(payload.replace(b"\n", b"\r\n"), at=NOW).valid
    duplicate = b'{"contract_version":"opencare-trust-envelope/1","contract_version":"x"}'
    assert not validate_envelope_bytes(duplicate, at=NOW).valid


def test_expired_envelope_is_not_executable() -> None:
    envelope = build()
    result = validate_envelope_bytes(canonical_bytes(envelope), at=NOW + timedelta(minutes=6))
    assert result.reason_codes == ["envelope_expired"]


def test_receipt_integrity_and_subset_constraints() -> None:
    envelope = build()
    receipt = build_execution_receipt(
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
    valid = validate_receipt_bytes(canonical_bytes(receipt), envelope=envelope, at=NOW)
    assert valid.valid
    changed = receipt.model_dump(mode="json")
    changed["used_tools"] = ["brief.draft"]
    tampered = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
    invalid = validate_receipt_bytes(tampered, envelope=envelope, at=NOW)
    assert not invalid.valid


def test_safety_refusal_never_mints_envelope() -> None:
    denied = authority()
    denied.safety = SafetyDecision(
        decision="refuse",
        reason_codes=["medical_advice_request"],
        policy_version="safety-v1",
        evaluated_at=NOW,
        limitations=["No diagnosis."],
        required_notices=["Clinician review required."],
    )
    with pytest.raises(BuildRefused) as error:
        TrustedEnvelopeBuilder(denied, clock=lambda: NOW).build(request())
    assert error.value.reason_codes == ["safety_refused"]


def test_cross_platform_fixture_matches_canonical_bytes() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "agent_trust" / "canonical-vector.json").read_text(
            encoding="utf-8"
        )
    )
    envelope = build()
    rendered = canonical_bytes(envelope)
    assert len(rendered) == fixture["byte_length"]
    assert sha256_hex(rendered) == fixture["sha256"]
