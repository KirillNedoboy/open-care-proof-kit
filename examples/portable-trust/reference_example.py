"""Portable Trust reference example — SYNTHETIC / OFFLINE fixture only.

This script demonstrates the generic G4 trust protocol with nothing but
synthetic/offline inputs: a fixed synthetic ``AuthorizationSnapshot`` and
synthetic evidence feed ``TrustedEnvelopeBuilder``; the resulting
``TrustEnvelope`` is verified; then a synthetic ``ExecutionReceipt`` is built
and verified.

It intentionally shows no health-workflow complexity and grants nothing:
constructing a Snapshot locally does NOT grant access to a live OpenCare
installation. A real installation decides authorization through its own
``AuthorizationAdapter`` (e.g. ``app.agent.trust_adapter``) at runtime.

Run from the repository root:

    python examples/portable-trust/reference_example.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent_trust.api import (  # noqa: E402
    AuthorizationDecision,
    AuthorizationSnapshot,
    EnvelopeRequest,
    EvidenceItem,
    SafetyDecision,
    TrustedEnvelopeBuilder,
    canonical_bytes,
    sha256_hex,
    validate_envelope_bytes,
    validate_receipt_bytes,
)
from app.agent_trust.builders import (  # noqa: E402
    TrustAuthority,
    build_execution_receipt,
)

NOW = datetime(2027, 8, 2, 10, 0, 0, tzinfo=UTC)

#: Fixed synthetic identifiers — not real Actors, People, or consent events.
ACTOR_ID = "actor-alice"
CREDENTIAL_ID = "credential-alice"
PERSON_ID = "person-alice"
CONSENT_BASIS_ID = "consent-alice"


class ReferenceAuthority:
    """Minimal offline TrustAuthority bound to one fixed synthetic snapshot.

    This is a demonstration stub, not a security boundary: it always allows the
    fixed synthetic identity. A live OpenCare installation never uses it.
    """

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        assert (actor_id, credential_id, person_id) == (
            ACTOR_ID,
            CREDENTIAL_ID,
            PERSON_ID,
        )
        return AuthorizationDecision(
            decision="allow",
            reason_codes=[],
            snapshot=AuthorizationSnapshot(
                actor_id=actor_id,
                credential_id=credential_id,
                person_id=person_id,
                assignment_id="assignment-alice",
                role="caregiver",
                granted_scopes=sorted(
                    {
                        "brief.read",
                        "chat.use",
                        "person.read",
                        "source.read",
                        "timeline.read",
                        "visit.read",
                    }
                ),
                required_scopes=sorted(required_scopes),
                consent_event_id=CONSENT_BASIS_ID,
                authorized_at=authorized_at,
                access_expires_at=None,
                policy_version="family-access-v1",
            ),
        )

    def select_evidence(
        self,
        *,
        evidence_ids: list[str],
        person_id: str,
        required_scopes: frozenset[str],
        observed_at: datetime,
    ) -> list[EvidenceItem]:
        assert person_id == PERSON_ID
        assert "source.read" in required_scopes
        return [
            EvidenceItem(
                evidence_id=evidence_id,
                evidence_type="medication_record",
                person_id=person_id,
                resource_scope="source.read",
                content_sha256=sha256_hex(b"synthetic medication record"),
                source_ids=["source-alice"],
                provenance_status="source_backed",
                selected_fields=["medication.name", "medication.status"],
                observed_at=observed_at,
            )
            for evidence_id in evidence_ids
        ]

    def safety_decision(self, request: EnvelopeRequest, evaluated_at: datetime) -> SafetyDecision:
        return SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="safety-v1",
            evaluated_at=evaluated_at,
            limitations=["Recorded context only; no diagnosis or treatment advice."],
            required_notices=["Clinician review is required."],
        )

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        return None


def main() -> int:
    request = EnvelopeRequest(
        actor_id=ACTOR_ID,
        credential_id=CREDENTIAL_ID,
        person_id=PERSON_ID,
        purpose_id="visit_preparation",
        action_id="summarize_records",
        requested_action="Summarize selected records for visit preparation.",
        requested_tools=["context.read", "source.read"],
        evidence_ids=["evidence-medication-alice"],
        disclosure_mode="local_only",
        provider_id=None,
        consent_basis_id=CONSENT_BASIS_ID,
        ttl_seconds=300,
    )
    envelope = TrustedEnvelopeBuilder(ReferenceAuthority(), clock=lambda: NOW).build(request)
    envelope_result = validate_envelope_bytes(canonical_bytes(envelope), at=NOW)
    assert envelope_result.valid, envelope_result.reason_codes

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
    receipt_result = validate_receipt_bytes(
        canonical_bytes(receipt), envelope=envelope, at=NOW
    )
    assert receipt_result.valid, receipt_result.reason_codes

    print(
        json.dumps(
            {
                "synthetic_offline_fixture_only": True,
                "not_live_authorization": True,
                "envelope_id": envelope.envelope_id,
                "envelope_valid": envelope_result.valid,
                "receipt_id": receipt.receipt_id,
                "receipt_valid": receipt_result.valid,
                "note": (
                    "Constructing a Snapshot locally grants no access to a live "
                    "OpenCare installation; authorization is decided by the "
                    "installation's own AuthorizationAdapter at runtime."
                ),
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
