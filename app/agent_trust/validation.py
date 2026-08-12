from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from app.agent_trust.canonical import (
    canonical_bytes,
    digest_matches,
    envelope_id,
    receipt_id,
    receipt_sha256,
    strict_json_loads,
)
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason_codes: list[str]
    envelope_id: str | None = None
    receipt_id: str | None = None


def validate_envelope_bytes(data: bytes, *, at: datetime) -> ValidationResult:
    try:
        raw = data[:-1] if data.endswith(b"\n") else data
        strict_json_loads(raw)
        envelope = TrustEnvelope.model_validate_json(raw, strict=False)
    except (ValueError, TypeError, ValidationError):
        return ValidationResult(False, ["invalid_contract"])
    reasons: list[str] = []
    if data not in (canonical_bytes(envelope), canonical_bytes(envelope) + b"\n"):
        reasons.append("non_canonical_document")
    expected = envelope_id(envelope)
    if not digest_matches(envelope.envelope_id, expected):
        reasons.append("envelope_id_mismatch")
    if at >= envelope.expires_at:
        reasons.append("envelope_expired")
    return ValidationResult(
        not reasons,
        sorted(reasons),
        envelope_id=envelope.envelope_id,
    )


def validate_receipt_bytes(
    data: bytes,
    *,
    envelope: TrustEnvelope | None,
    at: datetime,
) -> ValidationResult:
    del at
    try:
        raw = data[:-1] if data.endswith(b"\n") else data
        strict_json_loads(raw)
        receipt = ExecutionReceipt.model_validate_json(raw, strict=False)
    except (ValueError, TypeError, ValidationError):
        return ValidationResult(False, ["invalid_contract"])
    reasons: list[str] = []
    if data not in (canonical_bytes(receipt), canonical_bytes(receipt) + b"\n"):
        reasons.append("non_canonical_document")
    if not digest_matches(receipt.receipt_id, receipt_id(receipt)):
        reasons.append("receipt_id_mismatch")
    if not digest_matches(receipt.receipt_sha256, receipt_sha256(receipt)):
        reasons.append("receipt_hash_mismatch")
    if envelope is not None:
        exceeds = (
            receipt.envelope_id != envelope.envelope_id
            or not set(receipt.used_evidence_ids)
            <= set(envelope.provider_disclosure.allowed_evidence_ids)
            or not set(receipt.used_tools) <= set(envelope.allowed_tools)
            or receipt.provider_id != envelope.provider_disclosure.provider_id
            or receipt.started_at < envelope.issued_at
            or receipt.completed_at > envelope.expires_at
        )
        if exceeds:
            reasons.append("receipt_exceeds_envelope")
    return ValidationResult(
        not reasons,
        sorted(set(reasons)),
        receipt_id=receipt.receipt_id,
    )
