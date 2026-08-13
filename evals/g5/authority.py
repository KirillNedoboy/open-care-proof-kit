"""Extended synthetic trust authority for the G5 adversarial corpus.

``app.agent_trust.testing.SyntheticAuthority`` covers a single happy path plus
Carole isolation. The G5 corpus additionally needs *multiple* actors (Bob,
Carol), extra Person evidence for disclosure-minimization, and mutable live
state so the harness can revoke assignments / consents or mutate context
between the G2 prepare → grant → execute phases.

This is eval-only scaffolding. It implements the exact ``TrustAuthority``
protocol that ``TrustedEnvelopeBuilder`` consumes and that the real
``app.agent.trust_adapter.OpenCareAuthorizationAdapter`` satisfies in
production, so the same builder path is exercised. It never grants real access
and never touches the Product Core database.

Synthetic identities only: ``actor-alice``/``actor-bob``/``actor-carol`` and
``person-alice``/``person-bob``/``person-carol``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.agent.providers.contract import ProviderDescriptor
from app.agent_trust.builders import BuildRefused, EnvelopeRequest
from app.agent_trust.canonical import sha256_hex
from app.agent_trust.models import (
    AuthorizationDecision,
    AuthorizationSnapshot,
    EvidenceItem,
    SafetyDecision,
)

#: All scopes the synthetic actors are granted (superset of every action's
#: required scopes in ``app.agent_trust.identifiers``).
ALL_SCOPES = frozenset(
    {
        "brief.read",
        "chat.use",
        "person.read",
        "source.read",
        "timeline.read",
        "visit.read",
    }
)

DEFAULT_SELECTED_FIELDS = ("record.summary",)


@dataclass
class AccessRecord:
    actor_id: str
    person_id: str
    assignment_id: str
    consent_event_id: str
    role: str
    granted_scopes: frozenset[str]
    state: str = "active"
    expires_at: datetime | None = None


@dataclass
class EvidenceRecord:
    person_id: str
    source_ids: list[str]
    content: bytes
    selected_fields: tuple[str, ...] = DEFAULT_SELECTED_FIELDS


class G5Authority:
    """Mutable synthetic authority implementing the ``TrustAuthority`` protocol."""

    def __init__(self, *, allow_external_disclosure: bool = False) -> None:
        self.allow_external_disclosure = allow_external_disclosure
        self.access: dict[str, AccessRecord] = {}
        self.evidence: dict[str, EvidenceRecord] = {}
        #: Live consent state per ``(actor_id, person_id)``. Revoking this is
        #: how the harness models post-consent revocation (G2 surfaces it as a
        #: context change through the revalidate gate).
        self.consent_state: dict[tuple[str, str], str] = {}
        self._safety = SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="safety-v1",
            evaluated_at=datetime(2027, 8, 2, 10, 0, 0, tzinfo=UTC),
            limitations=["Recorded context only; no diagnosis or treatment advice."],
            required_notices=["Clinician review is required."],
        )

    # -- seeding -----------------------------------------------------------

    def add_actor(
        self,
        *,
        actor_id: str,
        person_id: str,
        assignment_id: str,
        consent_event_id: str,
        role: str = "caregiver",
        state: str = "active",
        expires_at: datetime | None = None,
    ) -> None:
        self.access[actor_id] = AccessRecord(
            actor_id=actor_id,
            person_id=person_id,
            assignment_id=assignment_id,
            consent_event_id=consent_event_id,
            role=role,
            granted_scopes=ALL_SCOPES,
            state=state,
            expires_at=expires_at,
        )
        self.consent_state[(actor_id, person_id)] = "active"

    def add_evidence(
        self,
        *,
        evidence_id: str,
        person_id: str,
        source_ids: list[str],
        content: bytes,
        selected_fields: tuple[str, ...] = DEFAULT_SELECTED_FIELDS,
    ) -> None:
        self.evidence[evidence_id] = EvidenceRecord(
            person_id=person_id,
            source_ids=list(source_ids),
            content=content,
            selected_fields=selected_fields,
        )

    @classmethod
    def seeded(cls, *, now: datetime) -> G5Authority:
        """The standard corpus state: Alice (3 records), Bob, Carol, revoked.

        ``now`` only seeds expiry-shaped state; the harness drives every other
        mutation explicitly, so replay stays deterministic.
        """
        authority = cls()
        authority.add_actor(
            actor_id="actor-alice",
            person_id="person-alice",
            assignment_id="assignment-alice",
            consent_event_id="consent-alice",
        )
        authority.add_actor(
            actor_id="actor-bob",
            person_id="person-bob",
            assignment_id="assignment-bob",
            consent_event_id="consent-bob",
        )
        authority.add_actor(
            actor_id="actor-carol",
            person_id="person-carol",
            assignment_id="assignment-carol",
            consent_event_id="consent-carol",
        )
        authority.add_actor(
            actor_id="actor-revoked",
            person_id="person-alice",
            assignment_id="assignment-revoked",
            consent_event_id="consent-revoked",
            state="revoked",
        )
        authority.add_evidence(
            evidence_id="evidence-medication-alice",
            person_id="person-alice",
            source_ids=["source-alice"],
            content=b"synthetic alice medication record",
        )
        authority.add_evidence(
            evidence_id="evidence-lab-alice",
            person_id="person-alice",
            source_ids=["source-alice"],
            content=b"synthetic alice lab record",
        )
        authority.add_evidence(
            evidence_id="evidence-visit-alice",
            person_id="person-alice",
            source_ids=["source-alice"],
            content=b"synthetic alice visit record",
        )
        authority.add_evidence(
            evidence_id="evidence-medication-carol",
            person_id="person-carol",
            source_ids=["source-carol"],
            content=b"synthetic carol medication record",
        )
        authority.add_evidence(
            evidence_id="evidence-medication-bob",
            person_id="person-bob",
            source_ids=["source-bob"],
            content=b"synthetic bob medication record",
        )
        authority.add_evidence(
            evidence_id="evidence-missing-provenance",
            person_id="person-alice",
            source_ids=[],
            content=b"unprovenanced record",
        )
        authority._safety = SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="safety-v1",
            evaluated_at=now,
            limitations=["Recorded context only; no diagnosis or treatment advice."],
            required_notices=["Clinician review is required."],
        )
        return authority

    # -- live mutation (used by corpus phases) -----------------------------

    def revoke_actor(self, actor_id: str) -> None:
        record = self.access[actor_id]
        record.state = "revoked"

    def revoke_consent(self, actor_id: str, person_id: str) -> None:
        self.consent_state[(actor_id, person_id)] = "revoked"

    def mutate_evidence_content(self, evidence_id: str, content: bytes) -> None:
        record = self.evidence[evidence_id]
        record.content = content

    def consent_is_active(self, actor_id: str, person_id: str) -> bool:
        return self.consent_state.get((actor_id, person_id), "active") == "active"

    # -- TrustAuthority protocol ------------------------------------------

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        record = self.access.get(actor_id)
        if record is None or record.person_id != person_id:
            return AuthorizationDecision(
                decision="deny", reason_codes=["person_access_denied"], snapshot=None
            )
        if record.state == "revoked":
            return AuthorizationDecision(
                decision="deny", reason_codes=["authorization_revoked"], snapshot=None
            )
        if record.expires_at is not None and record.expires_at <= authorized_at:
            return AuthorizationDecision(
                decision="deny", reason_codes=["authorization_expired"], snapshot=None
            )
        if not required_scopes <= record.granted_scopes:
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
                assignment_id=record.assignment_id,
                role=record.role,  # type: ignore[arg-type]
                granted_scopes=sorted(record.granted_scopes),
                required_scopes=sorted(required_scopes),
                consent_event_id=record.consent_event_id,
                authorized_at=authorized_at,
                access_expires_at=record.expires_at,
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
            record = self.evidence.get(evidence_id)
            if record is None:
                raise BuildRefused(["provenance_missing"])
            if record.person_id != person_id:
                raise BuildRefused(["evidence_person_mismatch"])
            if not record.source_ids:
                raise BuildRefused(["provenance_missing"])
            if "source.read" not in required_scopes:
                raise BuildRefused(["evidence_scope_invalid"])
            selected.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    evidence_type="record",
                    person_id=person_id,
                    resource_scope="source.read",
                    content_sha256=sha256_hex(record.content),
                    source_ids=list(record.source_ids),
                    provenance_status="source_backed",
                    selected_fields=list(record.selected_fields),
                    observed_at=observed_at,
                )
            )
        return selected

    def safety_decision(self, request: EnvelopeRequest, evaluated_at: datetime) -> SafetyDecision:
        del request, evaluated_at
        return self._safety

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        if request.disclosure_mode == "external_provider" and not self.allow_external_disclosure:
            raise BuildRefused(["provider_disclosure_denied"])



@dataclass
class DescriptorBox:
    """Mutable provider identity bound into the Envelope disclosure.

    ``G2Runtime`` reads ``provider.descriptor`` to seed ``pending.provider_hash``
    and re-derives the envelope at consent/execute time. Swapping ``provider_id``
    or ``model_id`` here changes the descriptor hash and therefore the envelope
    identity, which is exactly the provider/model-swap TOCTOU the runtime must
    refuse.
    """

    provider_id: str
    model_id: str | None = None
    provider_kind: str = "deterministic"
    endpoint_class: str = "none"
    external: bool = False

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id=self.provider_id,
            provider_kind=self.provider_kind,
            provider_mode="local_only",
            endpoint_class=self.endpoint_class,
            external=self.external,
            model_id=self.model_id,
        )

    def swap_provider(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def swap_model(self, model_id: str) -> None:
        self.model_id = model_id


# Re-exported so corpus/harness modules share one definition.
__all__ = [
    "AccessRecord",
    "DEFAULT_SELECTED_FIELDS",
    "DescriptorBox",
    "EvidenceRecord",
    "G5Authority",
]
