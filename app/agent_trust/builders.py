from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from app.agent_trust.canonical import envelope_id, receipt_id, receipt_sha256, sha256_hex
from app.agent_trust.identifiers import (
    ACTION_REQUIREMENTS,
    DEFAULT_DISCLOSURE_CONSTRAINTS,
    PROHIBITED_OPERATIONS,
    ActionId,
    PurposeId,
    ToolId,
)
from app.agent_trust.models import (
    AuthorizationDecision,
    ContractModel,
    EvidenceItem,
    ExecutionReceipt,
    FinalDecision,
    ProviderDisclosure,
    SafetyDecision,
    TrustEnvelope,
)

MAX_TTL_SECONDS = 900


class BuildRefused(ValueError):
    def __init__(self, reason_codes: Sequence[str]) -> None:
        self.reason_codes = sorted(set(reason_codes))
        super().__init__(",".join(self.reason_codes))


class EnvelopeRequest(ContractModel):
    actor_id: str = Field(min_length=1, max_length=128)
    credential_id: str = Field(min_length=1, max_length=128)
    person_id: str = Field(min_length=1, max_length=128)
    purpose_id: PurposeId
    action_id: ActionId
    requested_action: str = Field(min_length=1, max_length=256)
    requested_tools: list[ToolId] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    disclosure_mode: Literal["local_only", "external_provider"]
    provider_id: str | None
    consent_basis_id: str = Field(min_length=1, max_length=128)
    ttl_seconds: int = Field(gt=0, le=MAX_TTL_SECONDS)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        for name in ("requested_tools", "evidence_ids"):
            values = getattr(self, name)
            if values != sorted(set(values)):
                raise ValueError(f"{name} must be sorted and unique")
        if self.disclosure_mode == "local_only" and self.provider_id is not None:
            raise ValueError("local disclosure cannot name provider")
        if self.disclosure_mode == "external_provider" and self.provider_id is None:
            raise ValueError("external disclosure requires provider")
        _, action_tools = ACTION_REQUIREMENTS[self.action_id]
        if not set(self.requested_tools) <= action_tools:
            raise ValueError("requested tool is not allowed for action")
        return self


class TrustAuthority(Protocol):
    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision: ...

    def select_evidence(
        self,
        *,
        evidence_ids: Sequence[str],
        person_id: str,
        required_scopes: frozenset[str],
        observed_at: datetime,
    ) -> list[EvidenceItem]: ...

    def safety_decision(
        self, request: EnvelopeRequest, evaluated_at: datetime
    ) -> SafetyDecision: ...

    def validate_disclosure(self, request: EnvelopeRequest) -> None: ...


class TrustedEnvelopeBuilder:
    def __init__(self, authority: TrustAuthority, *, clock: Callable[[], datetime]) -> None:
        self.authority = authority
        self.clock = clock

    def build(self, request: EnvelopeRequest) -> TrustEnvelope:
        now = self.clock()
        required_scopes, action_tools = ACTION_REQUIREMENTS[request.action_id]
        authorization = self.authority.authorize(
            actor_id=request.actor_id,
            credential_id=request.credential_id,
            person_id=request.person_id,
            required_scopes=required_scopes,
            authorized_at=now,
        )
        if authorization.decision != "allow" or authorization.snapshot is None:
            raise BuildRefused(authorization.reason_codes or ["person_access_denied"])
        snapshot = authorization.snapshot
        if snapshot.actor_id != request.actor_id or snapshot.person_id != request.person_id:
            raise BuildRefused(["person_mismatch"])
        if snapshot.credential_id != request.credential_id:
            raise BuildRefused(["authentication_required"])
        try:
            evidence = self.authority.select_evidence(
                evidence_ids=request.evidence_ids,
                person_id=request.person_id,
                required_scopes=required_scopes,
                observed_at=now,
            )
        except BuildRefused:
            raise
        if not evidence:
            raise BuildRefused(["provenance_missing"])
        evidence.sort(key=lambda item: item.evidence_id)
        safety = self.authority.safety_decision(request, now)
        if safety.decision != "allow":
            raise BuildRefused(["safety_refused"])
        self.authority.validate_disclosure(request)
        expires_at = now + timedelta(seconds=request.ttl_seconds)
        if snapshot.access_expires_at is not None:
            expires_at = min(expires_at, snapshot.access_expires_at)
        if expires_at <= now:
            raise BuildRefused(["authorization_expired"])
        allowed_tools = sorted(set(request.requested_tools) & action_tools)
        allowed_fields = sorted({field for item in evidence for field in item.selected_fields})
        disclosure = ProviderDisclosure(
            mode=request.disclosure_mode,
            provider_id=request.provider_id,
            consent_basis_id=request.consent_basis_id,
            allowed_evidence_ids=[item.evidence_id for item in evidence],
            allowed_fields=allowed_fields,
            prohibited_data_classes=["credentials", "raw_session_tokens", "unselected_sources"],
            retention="request_only"
            if request.disclosure_mode == "local_only"
            else "provider_policy",
        )
        payload = {
            "contract_version": "opencare-trust-envelope/1",
            "envelope_id": f"sha256:{'0' * 64}",
            "issued_at": now,
            "expires_at": expires_at,
            "actor_id": request.actor_id,
            "person_id": request.person_id,
            "purpose_id": request.purpose_id,
            "action_id": request.action_id,
            "requested_action": request.requested_action,
            "resource_scopes": sorted(required_scopes),
            "authorization": authorization,
            "safety": safety,
            "final_decision": FinalDecision(decision="allow", reason_codes=[]),
            "evidence": evidence,
            "provider_disclosure": disclosure,
            "allowed_tools": allowed_tools,
            "prohibited_operations": sorted(PROHIBITED_OPERATIONS),
            "disclosure_constraints": sorted(DEFAULT_DISCLOSURE_CONSTRAINTS),
            "limitations": safety.limitations,
            "safety_notices": safety.required_notices,
        }
        provisional = TrustEnvelope.model_validate(payload)
        payload["envelope_id"] = envelope_id(provisional)
        return TrustEnvelope.model_validate(payload)


def build_execution_receipt(
    *,
    envelope: TrustEnvelope,
    started_at: datetime,
    completed_at: datetime,
    status: Literal["completed", "refused", "failed"],
    provider_id: str | None,
    used_evidence_ids: list[str],
    used_tools: list[ToolId],
    output: bytes | None = None,
    reason_codes: list[str],
) -> ExecutionReceipt:
    if not set(used_evidence_ids) <= set(envelope.provider_disclosure.allowed_evidence_ids):
        raise BuildRefused(["receipt_exceeds_envelope"])
    if not set(used_tools) <= set(envelope.allowed_tools):
        raise BuildRefused(["receipt_exceeds_envelope"])
    if provider_id != envelope.provider_disclosure.provider_id:
        raise BuildRefused(["receipt_exceeds_envelope"])
    payload = {
        "contract_version": "opencare-execution-receipt/1",
        "receipt_id": f"sha256:{'0' * 64}",
        "envelope_id": envelope.envelope_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,
        "provider_id": provider_id,
        "used_evidence_ids": sorted(used_evidence_ids),
        "used_tools": sorted(used_tools),
        "output_sha256": sha256_hex(output) if output is not None else None,
        "reason_codes": sorted(reason_codes),
        "receipt_sha256": "0" * 64,
    }
    provisional = ExecutionReceipt.model_validate(payload)
    payload["receipt_id"] = receipt_id(provisional)
    with_identity = ExecutionReceipt.model_validate(payload)
    payload["receipt_sha256"] = receipt_sha256(with_identity)
    return ExecutionReceipt.model_validate(payload)
