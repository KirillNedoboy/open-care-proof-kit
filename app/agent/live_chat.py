"""OpenCare-specific authority and evidence projection for live chat."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

from app.agent.context import build_product_core_agent_context
from app.agent.models import AgentContext
from app.agent.policy import classify_question
from app.agent.providers.contract import AgentProvider
from app.agent.trust_adapter import OpenCareAuthorizationAdapter
from app.agent_trust.builders import (
    BuildRefused,
    EnvelopeRequest,
    TrustAuthority,
    TrustedEnvelopeBuilder,
)
from app.agent_trust.canonical import canonical_bytes, sha256_hex
from app.agent_trust.identifiers import ACTION_REQUIREMENTS, ActionId, PurposeId, ToolId
from app.agent_trust.models import (
    AuthorizationDecision,
    EvidenceItem,
    ProviderDescriptorContract,
    SafetyDecision,
    TrustEnvelope,
)
from app.family_access.service import FamilyAccessService
from app.product_core.runtime import ProductCoreRuntime

MAX_LIVE_CHAT_EVIDENCE_ITEMS = 100
LIVE_CHAT_PURPOSE = "record_explanation"
LIVE_CHAT_ACTION = "answer_question"
LIVE_CHAT_REQUESTED_ACTION = (
    "Explain selected recorded evidence without changing canonical records."
)
LIVE_CHAT_CONSENT_BASIS = "live-chat-disclosure-v1"
LIVE_CHAT_KINDS = frozenset({"medication", "condition", "lab", "timeline"})


def project_live_chat_evidence(
    context: AgentContext,
    person_id: str,
    observed_at: datetime,
) -> tuple[list[EvidenceItem], tuple[dict[str, Any], ...]]:
    """Project only source-backed, non-genetic Product Core context values."""
    if observed_at.tzinfo is None or observed_at.utcoffset() != UTC.utcoffset(observed_at):
        raise ValueError("observed_at must use UTC")
    projected: list[tuple[EvidenceItem, dict[str, Any]]] = []
    for item in context.items:
        if (
            item.provenance_status != "source_backed"
            or not item.source_ids
            or item.kind not in LIVE_CHAT_KINDS
        ):
            continue
        selected_fields = (f"{item.kind}.text",)
        value = {
            "evidence_id": item.id,
            "person_id": person_id,
            "kind": item.kind,
            "text": item.text,
            "selected_fields": selected_fields,
            "source_ids": tuple(sorted(set(item.source_ids))),
        }
        projected.append(
            (
                EvidenceItem(
                    evidence_id=item.id,
                    evidence_type=f"{item.kind}_record",
                    person_id=person_id,
                    resource_scope="source.read",
                    content_sha256=sha256_hex(canonical_bytes(value)),
                    source_ids=list(value["source_ids"]),
                    provenance_status="source_backed",
                    selected_fields=list(selected_fields),
                    observed_at=observed_at,
                ),
                value,
            )
        )
    projected.sort(key=lambda pair: pair[0].evidence_id)
    if len(projected) > MAX_LIVE_CHAT_EVIDENCE_ITEMS:
        raise BuildRefused(["context_limit_exceeded"])
    return [item for item, _ in projected], tuple(value for _, value in projected)


def current_live_chat_evidence(
    runtime: ProductCoreRuntime,
    person_id: str,
    observed_at: datetime,
) -> tuple[list[EvidenceItem], tuple[dict[str, Any], ...]]:
    context = build_product_core_agent_context(runtime, person_id)
    return project_live_chat_evidence(context, person_id, observed_at)


def resolve_live_chat_evidence(
    runtime: ProductCoreRuntime,
    envelope: TrustEnvelope,
    observed_at: datetime,
) -> tuple[dict[str, Any], ...]:
    evidence, values = current_live_chat_evidence(runtime, envelope.person_id, observed_at)
    by_id = {item.evidence_id: item for item in evidence}
    value_by_id = {str(value["evidence_id"]): value for value in values}
    resolved: list[dict[str, Any]] = []
    for item in envelope.evidence:
        current = by_id.get(item.evidence_id)
        value = value_by_id.get(item.evidence_id)
        if current is None or value is None:
            raise BuildRefused(["context_changed"])
        if current.content_sha256 != item.content_sha256:
            raise BuildRefused(["context_changed"])
        resolved.append(value)
    return tuple(resolved)


class LiveChatAuthority(TrustAuthority):
    """Build a live Envelope from current Family Access and Product Core state."""

    def __init__(
        self,
        product_runtime: ProductCoreRuntime,
        family_service: FamilyAccessService,
        provider: AgentProvider,
        *,
        question: str,
        clock: Callable[[], datetime],
    ) -> None:
        self.product_runtime = product_runtime
        self.family_service = family_service
        self.provider = provider
        self.question = question
        self.clock = clock
        self.adapter = OpenCareAuthorizationAdapter(family_service)

    def build_envelope(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
    ) -> TrustEnvelope:
        evidence, _ = current_live_chat_evidence(self.product_runtime, person_id, self.clock())
        descriptor = self.provider.descriptor
        provider_descriptor = ProviderDescriptorContract(
            provider_id=descriptor.provider_id,
            model_id=descriptor.model_id,
            provider_kind=descriptor.provider_kind,
            endpoint_class=descriptor.endpoint_class,
            external=descriptor.external,
            descriptor_hash=descriptor.descriptor_hash,
        )
        disclosure_mode = "external_provider" if descriptor.external else "local_only"
        builder = TrustedEnvelopeBuilder(self, clock=self.clock)
        return builder.build(
            EnvelopeRequest(
                actor_id=actor_id,
                credential_id=credential_id,
                person_id=person_id,
                purpose_id=cast(PurposeId, LIVE_CHAT_PURPOSE),
                action_id=cast(ActionId, LIVE_CHAT_ACTION),
                requested_action=LIVE_CHAT_REQUESTED_ACTION,
                requested_tools=cast(
                    list[ToolId], sorted(ACTION_REQUIREMENTS[LIVE_CHAT_ACTION][1])
                ),
                evidence_ids=[item.evidence_id for item in evidence],
                disclosure_mode=cast(
                    Literal["local_only", "external_provider"], disclosure_mode
                ),
                provider_id=descriptor.provider_id,
                provider_descriptor=provider_descriptor,
                consent_basis_id=LIVE_CHAT_CONSENT_BASIS,
                ttl_seconds=300,
            )
        )

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        return self.adapter.authorize(
            actor_id=actor_id,
            credential_id=credential_id,
            person_id=person_id,
            required_scopes=required_scopes,
            authorized_at=authorized_at,
        )

    def select_evidence(
        self,
        *,
        evidence_ids: Sequence[str],
        person_id: str,
        required_scopes: frozenset[str],
        observed_at: datetime,
    ) -> list[EvidenceItem]:
        if "source.read" not in required_scopes:
            raise BuildRefused(["evidence_scope_invalid"])
        evidence, _ = current_live_chat_evidence(self.product_runtime, person_id, observed_at)
        by_id = {item.evidence_id: item for item in evidence}
        selected: list[EvidenceItem] = []
        for evidence_id in evidence_ids:
            item = by_id.get(evidence_id)
            if item is None:
                raise BuildRefused(["provenance_missing"])
            selected.append(item)
        return selected

    def safety_decision(self, request: EnvelopeRequest, evaluated_at: datetime) -> SafetyDecision:
        policy = classify_question(self.question)
        if policy.decision != "allowed":
            return SafetyDecision(
                decision="refuse",
                reason_codes=[policy.reason_code or "policy_refusal"],
                policy_version="live-chat-safety-v1",
                evaluated_at=evaluated_at,
                limitations=["The question is outside OpenCare's bounded evidence mode."],
                required_notices=[policy.response_text],
            )
        del request
        return SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="live-chat-safety-v1",
            evaluated_at=evaluated_at,
            limitations=[
                "Only selected, source-backed recorded context is available.",
                "OpenCare is not a diagnostic or treatment authority.",
            ],
            required_notices=[
                "No diagnosis, treatment, dosage, or medication start/stop advice is provided."
            ],
        )

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        if request.disclosure_mode == "external_provider" and not request.provider_descriptor:
            raise BuildRefused(["provider_disclosure_denied"])
