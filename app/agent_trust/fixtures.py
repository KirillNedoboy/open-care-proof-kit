"""Deterministic portable trust fixtures for ``fixtures/agent-trust/``.

All fixtures are SYNTHETIC / OFFLINE. They are built from the trusted synthetic
builders (``SyntheticAuthority.allowed``, ``TrustedEnvelopeBuilder``,
``build_execution_receipt``) plus the canonical helpers, never from hand-authored
hashes. They carry NO authorization power and NO real health data: a fixture
Snapshot/Envelope/Receipt does not grant access to a live OpenCare installation.

The fixed clock (``FIXTURE_NOW``) makes regeneration byte-identical across time
and platform. Regenerate with the ``opencare-trust regenerate-fixtures`` CLI
command (or ``app.agent_trust.cli`` ``main(["regenerate-fixtures"])``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.agent_trust.builders import (
    EnvelopeRequest,
    TrustedEnvelopeBuilder,
    build_execution_receipt,
)
from app.agent_trust.canonical import canonical_bytes, receipt_id, receipt_sha256
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope
from app.agent_trust.testing import SyntheticAuthority

#: Fixed synthetic clock so regenerated fixtures are byte-identical forever.
FIXTURE_NOW = datetime(2027, 8, 2, 10, 0, 0, tzinfo=UTC)

ENVELOPE_FILENAME = "allowed-envelope.json"
RECEIPT_FILENAME = "allowed-receipt.json"
REFUSED_RECEIPT_FILENAME = "refused-before-envelope-receipt.json"
UNSUPPORTED_RECEIPT_FILENAME = "unsupported-action-receipt.json"

FIXTURE_FILENAMES = (
    ENVELOPE_FILENAME,
    RECEIPT_FILENAME,
    REFUSED_RECEIPT_FILENAME,
    UNSUPPORTED_RECEIPT_FILENAME,
)


def allowed_envelope() -> TrustEnvelope:
    """The synthetic allowed Envelope (person-alice, summarize_records)."""
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
    return TrustedEnvelopeBuilder(
        SyntheticAuthority.allowed(now=FIXTURE_NOW), clock=lambda: FIXTURE_NOW
    ).build(request)


def allowed_receipt() -> ExecutionReceipt:
    """Completed synthetic Receipt linked to the allowed Envelope."""
    envelope = allowed_envelope()
    return build_execution_receipt(
        envelope=envelope,
        started_at=envelope.issued_at + timedelta(seconds=1),
        completed_at=envelope.issued_at + timedelta(seconds=2),
        status="completed",
        provider_id=None,
        used_evidence_ids=["evidence-medication-alice"],
        used_tools=["context.read"],
        output=b"safe output",
        reason_codes=[],
    )


def refused_before_envelope_receipt() -> ExecutionReceipt:
    """Refused Receipt: same Envelope link, but execution never completed.

    A Receipt alone does not prove a completed Envelope: this artifact records a
    refusal (status ``refused``, no ``output_sha256``, explicit reason codes)
    even though it references the same Envelope identity as the allowed Receipt.
    """
    envelope = allowed_envelope()
    return build_execution_receipt(
        envelope=envelope,
        started_at=envelope.issued_at + timedelta(seconds=1),
        completed_at=envelope.issued_at + timedelta(seconds=2),
        status="refused",
        provider_id=None,
        used_evidence_ids=["evidence-medication-alice"],
        used_tools=["context.read"],
        output=None,
        reason_codes=["safety_refused"],
    )


def unsupported_action_receipt() -> ExecutionReceipt:
    """Fail-closed refusal for an unsupported action.

    An unsupported action never receives an Envelope, so this Receipt links to a
    placeholder Envelope identity (``sha256:`` + 64 zeros) that corresponds to
    no real Envelope. It is built with the canonical helpers (``receipt_id`` /
    ``receipt_sha256``), not hand-authored hashes, and refuses with the stable
    ``unsupported_action`` reason code.
    """
    payload: dict[str, object] = {
        "contract_version": "opencare-execution-receipt/1",
        "receipt_id": f"sha256:{'0' * 64}",
        "envelope_id": f"sha256:{'0' * 64}",
        "started_at": FIXTURE_NOW,
        "completed_at": FIXTURE_NOW + timedelta(seconds=1),
        "status": "refused",
        "provider_id": None,
        "model_id": None,
        "provider_kind": None,
        "external": None,
        "used_evidence_ids": [],
        "used_tools": [],
        "output_sha256": None,
        "reason_codes": ["unsupported_action"],
        "receipt_sha256": "0" * 64,
    }
    provisional = ExecutionReceipt.model_validate(payload)
    payload["receipt_id"] = receipt_id(provisional)
    with_identity = ExecutionReceipt.model_validate(payload)
    payload["receipt_sha256"] = receipt_sha256(with_identity)
    return ExecutionReceipt.model_validate(payload)


def generate_fixtures() -> dict[str, bytes]:
    """Return {filename: canonical JSON bytes + LF} for the committed fixtures."""
    return {
        ENVELOPE_FILENAME: canonical_bytes(allowed_envelope()) + b"\n",
        RECEIPT_FILENAME: canonical_bytes(allowed_receipt()) + b"\n",
        REFUSED_RECEIPT_FILENAME: canonical_bytes(refused_before_envelope_receipt()) + b"\n",
        UNSUPPORTED_RECEIPT_FILENAME: canonical_bytes(unsupported_action_receipt()) + b"\n",
    }


def default_fixtures_dir() -> Path:
    """Repo-owned fixtures directory (``<repo>/fixtures/agent-trust``)."""
    return Path(__file__).resolve().parents[2] / "fixtures" / "agent-trust"


def write_fixtures(output_dir: Path) -> list[Path]:
    """Write the four JSON fixtures into ``output_dir``; returns written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, content in generate_fixtures().items():
        target = output_dir / filename
        target.write_bytes(content)
        written.append(target)
    return written
