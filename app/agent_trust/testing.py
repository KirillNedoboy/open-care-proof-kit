from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self

from app.agent_trust.builders import BuildRefused, EnvelopeRequest
from app.agent_trust.canonical import sha256_hex
from app.agent_trust.models import (
    AuthorizationDecision,
    AuthorizationSnapshot,
    EvidenceItem,
    SafetyDecision,
)


@dataclass
class SyntheticAccess:
    actor_id: str
    person_id: str
    assignment_id: str
    consent_event_id: str
    role: str
    granted_scopes: frozenset[str]
    state: str = "active"
    expires_at: datetime | None = None


class SyntheticAuthority:
    def __init__(self, *, allow_external_disclosure: bool = False) -> None:
        self.access: dict[str, SyntheticAccess] = {}
        self.evidence: dict[str, dict[str, object]] = {}
        self.safety: SafetyDecision
        self.allow_external_disclosure = allow_external_disclosure

    @classmethod
    def allowed(cls, *, now: datetime, allow_external_disclosure: bool = False) -> Self:
        authority = cls(allow_external_disclosure=allow_external_disclosure)
        all_scopes = frozenset(
            {
                "brief.read",
                "chat.use",
                "person.read",
                "source.read",
                "timeline.read",
                "visit.read",
            }
        )
        authority.access = {
            "actor-alice": SyntheticAccess(
                actor_id="actor-alice",
                person_id="person-alice",
                assignment_id="assignment-alice",
                consent_event_id="consent-alice",
                role="caregiver",
                granted_scopes=all_scopes,
            ),
            "actor-revoked": SyntheticAccess(
                actor_id="actor-revoked",
                person_id="person-alice",
                assignment_id="assignment-revoked",
                consent_event_id="consent-revoked",
                role="caregiver",
                granted_scopes=all_scopes,
                state="revoked",
            ),
            "actor-expired": SyntheticAccess(
                actor_id="actor-expired",
                person_id="person-alice",
                assignment_id="assignment-expired",
                consent_event_id="consent-expired",
                role="caregiver",
                granted_scopes=all_scopes,
                expires_at=now - timedelta(seconds=1),
            ),
        }
        authority.evidence = {
            "evidence-medication-alice": {
                "person_id": "person-alice",
                "source_ids": ["source-alice"],
                "content": b"synthetic medication record",
            },
            "evidence-medication-carol": {
                "person_id": "person-carol",
                "source_ids": ["source-carol"],
                "content": b"synthetic Carol record",
            },
            "evidence-missing-provenance": {
                "person_id": "person-alice",
                "source_ids": [],
                "content": b"unprovenanced record",
            },
        }
        authority.safety = SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="safety-v1",
            evaluated_at=now,
            limitations=["Recorded context only; no diagnosis or treatment advice."],
            required_notices=["Clinician review is required."],
        )
        return authority

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        access = self.access.get(actor_id)
        if access is None or access.person_id != person_id:
            return AuthorizationDecision(
                decision="deny", reason_codes=["person_access_denied"], snapshot=None
            )
        if access.state == "revoked":
            return AuthorizationDecision(
                decision="deny", reason_codes=["authorization_revoked"], snapshot=None
            )
        if access.expires_at is not None and access.expires_at <= authorized_at:
            return AuthorizationDecision(
                decision="deny", reason_codes=["authorization_expired"], snapshot=None
            )
        if not required_scopes <= access.granted_scopes:
            return AuthorizationDecision(
                decision="deny", reason_codes=["required_scope_missing"], snapshot=None
            )
        return AuthorizationDecision(
            decision="allow",
            reason_codes=[],
            snapshot=AuthorizationSnapshot(
                actor_id=actor_id,
                credential_id=credential_id,
                person_id=person_id,
                assignment_id=access.assignment_id,
                role=access.role,  # type: ignore[arg-type]
                granted_scopes=sorted(access.granted_scopes),
                required_scopes=sorted(required_scopes),
                consent_event_id=access.consent_event_id,
                authorized_at=authorized_at,
                access_expires_at=access.expires_at,
                policy_version="family-access-v1",
            ),
        )

    def select_evidence(
        self,
        *,
        evidence_ids: Sequence[str],
        person_id: str,
        required_scopes: frozenset[str],
        observed_at: datetime,
    ) -> list[EvidenceItem]:
        selected: list[EvidenceItem] = []
        for evidence_id in evidence_ids:
            item = self.evidence.get(evidence_id)
            if item is None:
                raise BuildRefused(["provenance_missing"])
            if item["person_id"] != person_id:
                raise BuildRefused(["evidence_person_mismatch"])
            source_ids = item["source_ids"]
            if not isinstance(source_ids, list) or not source_ids:
                raise BuildRefused(["provenance_missing"])
            if "source.read" not in required_scopes:
                raise BuildRefused(["evidence_scope_invalid"])
            content = item["content"]
            assert isinstance(content, bytes)
            selected.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    evidence_type="medication_record",
                    person_id=person_id,
                    resource_scope="source.read",
                    content_sha256=sha256_hex(content),
                    source_ids=source_ids,
                    provenance_status="source_backed",
                    selected_fields=["medication.name", "medication.status"],
                    observed_at=observed_at,
                )
            )
        return selected

    def safety_decision(self, request: EnvelopeRequest, evaluated_at: datetime) -> SafetyDecision:
        del request, evaluated_at
        return self.safety

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        if request.disclosure_mode == "external_provider" and not self.allow_external_disclosure:
            raise BuildRefused(["provider_disclosure_denied"])
