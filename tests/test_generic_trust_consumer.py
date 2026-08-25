"""Clean-room proof that a non-health consumer can use only app.agent_trust."""

from datetime import UTC, datetime

import pytest

from app.agent_trust.builders import (
    BuildRefused,
    EnvelopeRequest,
    TrustedEnvelopeBuilder,
    build_execution_receipt,
)
from app.agent_trust.canonical import sha256_hex
from app.agent_trust.models import (
    AuthorizationDecision,
    AuthorizationSnapshot,
    EvidenceItem,
    SafetyDecision,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)


class NoteAuthority:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        if not self.allowed:
            return AuthorizationDecision(
                decision="deny", reason_codes=["authorization_revoked"], snapshot=None
            )
        return AuthorizationDecision(
            decision="allow",
            reason_codes=[],
            snapshot=AuthorizationSnapshot(
                actor_id=actor_id,
                credential_id=credential_id,
                person_id=person_id,
                assignment_id="note-assignment",
                role="owner",
                granted_scopes=sorted(required_scopes),
                required_scopes=sorted(required_scopes),
                consent_event_id="note-consent",
                authorized_at=authorized_at,
                access_expires_at=None,
                policy_version="note-v1",
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
        if evidence_ids != ["note-1"] or person_id != "workspace-owner":
            raise BuildRefused(["provenance_missing"])
        return [
            EvidenceItem(
                evidence_id="note-1",
                evidence_type="private_note",
                person_id=person_id,
                resource_scope="source.read",
                content_sha256=sha256_hex(b"packing list"),
                source_ids=["note-source"],
                provenance_status="source_backed",
                selected_fields=["note.text"],
                observed_at=observed_at,
            )
        ]

    def safety_decision(
        self, request: EnvelopeRequest, evaluated_at: datetime
    ) -> SafetyDecision:
        return SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="note-safety-v1",
            evaluated_at=evaluated_at,
            limitations=["Private note only"],
            required_notices=["Review the note before relying on it."],
        )

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        return None


def _request() -> EnvelopeRequest:
    return EnvelopeRequest(
        actor_id="note-actor",
        credential_id="note-credential",
        person_id="workspace-owner",
        purpose_id="record_explanation",
        action_id="answer_question",
        requested_action="Explain a private packing note.",
        requested_tools=["context.read"],
        evidence_ids=["note-1"],
        disclosure_mode="local_only",
        provider_id="note-provider",
        consent_basis_id="note-consent-v1",
        ttl_seconds=300,
    )


def test_generic_consumer_builds_allowed_and_refused_artifacts_and_receipt() -> None:
    allowed = TrustedEnvelopeBuilder(NoteAuthority(), clock=lambda: NOW).build(_request())
    receipt = build_execution_receipt(
        envelope=allowed,
        started_at=NOW,
        completed_at=NOW,
        status="completed",
        provider_id="note-provider",
        model_id=None,
        provider_kind=None,
        external=None,
        used_evidence_ids=["note-1"],
        used_tools=[],
        output=b"safe answer",
        reason_codes=[],
    )
    assert receipt.status == "completed"
    with pytest.raises(BuildRefused, match="authorization_revoked"):
        TrustedEnvelopeBuilder(NoteAuthority(False), clock=lambda: NOW).build(_request())


def test_clean_room_source_has_no_opencare_or_web_runtime_imports() -> None:
    source = __import__("pathlib").Path(__file__).read_text(encoding="utf-8")
    for forbidden in (
        "app." + "product_core",
        "app." + "family_access",
        "app." + "genetics",
        "fast" + "api",
        "Sent" + "ient",
    ):
        assert forbidden not in source
