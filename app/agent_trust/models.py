from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.agent_trust.identifiers import ActionId, PurposeId, ToolId

CONTRACT_VERSION = "opencare-trust-envelope/1"
RECEIPT_VERSION = "opencare-execution-receipt/1"
IDENTITY_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

BoundedString = Annotated[str, StringConstraints(min_length=1, max_length=256)]
OpaqueId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, strip_whitespace=False),
]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ContentId = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @field_validator("*", mode="before")
    @classmethod
    def reject_invalid_strings(cls, value: object) -> object:
        def check(item: str) -> None:
            if item != item.strip() or any(ord(char) < 32 for char in item):
                raise ValueError("strings must be normalized and contain no control characters")
            try:
                item.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("strings must be valid Unicode") from exc

        if isinstance(value, str):
            check(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    check(item)
        return value

    @field_validator("*", mode="after")
    @classmethod
    def require_utc_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime) and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise ValueError("datetime must use UTC")
        return value


class AuthorizationSnapshot(ContractModel):
    actor_id: OpaqueId
    credential_id: OpaqueId
    person_id: OpaqueId
    assignment_id: OpaqueId
    role: Literal["owner", "caregiver"]
    granted_scopes: list[BoundedString] = Field(min_length=1)
    required_scopes: list[BoundedString] = Field(min_length=1)
    consent_event_id: OpaqueId
    authorized_at: datetime
    access_expires_at: datetime | None = None
    policy_version: BoundedString

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        _require_sorted_unique(self.granted_scopes, "granted_scopes")
        _require_sorted_unique(self.required_scopes, "required_scopes")
        if not set(self.required_scopes) <= set(self.granted_scopes):
            raise ValueError("required scopes must be granted")
        if self.access_expires_at is not None and self.access_expires_at <= self.authorized_at:
            raise ValueError("access must expire after authorization")
        return self


class AuthorizationDecision(ContractModel):
    decision: Literal["allow", "deny"]
    reason_codes: list[BoundedString]
    snapshot: AuthorizationSnapshot | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if self.decision == "allow" and (self.snapshot is None or self.reason_codes):
            raise ValueError("allowed authorization requires snapshot and no reasons")
        if self.decision == "deny" and (self.snapshot is not None or not self.reason_codes):
            raise ValueError("denied authorization requires reasons and no snapshot")
        return self


class SafetyDecision(ContractModel):
    decision: Literal["allow", "refuse"]
    reason_codes: list[BoundedString]
    policy_version: BoundedString
    evaluated_at: datetime
    limitations: list[BoundedString] = Field(min_length=1)
    required_notices: list[BoundedString] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        _require_sorted_unique(self.reason_codes, "reason_codes")
        _require_sorted_unique(self.limitations, "limitations")
        _require_sorted_unique(self.required_notices, "required_notices")
        if self.decision == "allow" and self.reason_codes:
            raise ValueError("allowed safety decision cannot have refusal reasons")
        if self.decision == "refuse" and not self.reason_codes:
            raise ValueError("refused safety decision requires reasons")
        return self


class FinalDecision(ContractModel):
    decision: Literal["allow", "refuse"]
    reason_codes: list[BoundedString]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if (self.decision == "allow") == bool(self.reason_codes):
            raise ValueError("final decision and reasons are inconsistent")
        return self


class EvidenceItem(ContractModel):
    evidence_id: OpaqueId
    evidence_type: BoundedString
    person_id: OpaqueId
    resource_scope: BoundedString
    content_sha256: Digest
    source_ids: list[OpaqueId] = Field(min_length=1)
    provenance_status: Literal["source_backed", "user_asserted"]
    selected_fields: list[BoundedString] = Field(min_length=1)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        _require_sorted_unique(self.source_ids, "source_ids")
        _require_sorted_unique(self.selected_fields, "selected_fields")
        return self


class ProviderDisclosure(ContractModel):
    mode: Literal["local_only", "external_provider"]
    provider_id: OpaqueId | None = None
    consent_basis_id: OpaqueId
    allowed_evidence_ids: list[OpaqueId]
    allowed_fields: list[BoundedString]
    prohibited_data_classes: list[BoundedString] = Field(min_length=1)
    retention: Literal["request_only", "provider_policy"]

    @model_validator(mode="after")
    def validate_disclosure(self) -> Self:
        _require_sorted_unique(self.allowed_evidence_ids, "allowed_evidence_ids")
        _require_sorted_unique(self.allowed_fields, "allowed_fields")
        _require_sorted_unique(self.prohibited_data_classes, "prohibited_data_classes")
        if self.mode == "local_only" and self.provider_id is not None:
            raise ValueError("local disclosure cannot name a provider")
        if self.mode == "external_provider" and self.provider_id is None:
            raise ValueError("external disclosure requires provider")
        return self


class TrustEnvelope(ContractModel):
    contract_version: Literal["opencare-trust-envelope/1"] = "opencare-trust-envelope/1"
    envelope_id: ContentId
    issued_at: datetime
    expires_at: datetime
    actor_id: OpaqueId
    person_id: OpaqueId
    purpose_id: PurposeId
    action_id: ActionId
    requested_action: BoundedString
    resource_scopes: list[BoundedString] = Field(min_length=1)
    authorization: AuthorizationDecision
    safety: SafetyDecision
    final_decision: FinalDecision
    evidence: list[EvidenceItem] = Field(min_length=1)
    provider_disclosure: ProviderDisclosure
    allowed_tools: list[ToolId] = Field(min_length=1)
    prohibited_operations: list[BoundedString] = Field(min_length=1)
    disclosure_constraints: list[BoundedString] = Field(min_length=1)
    limitations: list[BoundedString] = Field(min_length=1)
    safety_notices: list[BoundedString] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        for field_name in (
            "resource_scopes",
            "allowed_tools",
            "prohibited_operations",
            "disclosure_constraints",
            "limitations",
            "safety_notices",
        ):
            _require_sorted_unique(getattr(self, field_name), field_name)
        if self.expires_at <= self.issued_at:
            raise ValueError("Envelope expiry must follow issuance")
        snapshot = self.authorization.snapshot
        if (
            self.authorization.decision != "allow"
            or snapshot is None
            or self.safety.decision != "allow"
            or self.final_decision.decision != "allow"
        ):
            raise ValueError("issued Envelope decisions must allow")
        if self.actor_id != snapshot.actor_id or self.person_id != snapshot.person_id:
            raise ValueError("Envelope identity must match authorization")
        if self.resource_scopes != snapshot.required_scopes:
            raise ValueError("Envelope scopes must equal required scopes")
        if snapshot.access_expires_at is not None and self.expires_at > snapshot.access_expires_at:
            raise ValueError("Envelope cannot outlive access")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if evidence_ids != sorted(set(evidence_ids)):
            raise ValueError("evidence must be sorted and unique")
        if any(item.person_id != self.person_id for item in self.evidence):
            raise ValueError("evidence Person must match Envelope")
        if any(item.resource_scope not in self.resource_scopes for item in self.evidence):
            raise ValueError("evidence scope must be authorized")
        disclosure = self.provider_disclosure
        if disclosure.allowed_evidence_ids != evidence_ids:
            raise ValueError("disclosure evidence must equal selected evidence")
        selected_fields = sorted(
            {field for item in self.evidence for field in item.selected_fields}
        )
        if disclosure.allowed_fields != selected_fields:
            raise ValueError("disclosure fields must equal selected fields")
        if not set(self.safety.required_notices) <= set(self.safety_notices):
            raise ValueError("required safety notices must be retained")
        return self


class ExecutionReceipt(ContractModel):
    contract_version: Literal["opencare-execution-receipt/1"] = (
        "opencare-execution-receipt/1"
    )
    receipt_id: ContentId
    envelope_id: ContentId
    started_at: datetime
    completed_at: datetime
    status: Literal["completed", "refused", "failed"]
    provider_id: OpaqueId | None = None
    used_evidence_ids: list[OpaqueId]
    used_tools: list[ToolId]
    output_sha256: Digest | None = None
    reason_codes: list[BoundedString]
    receipt_sha256: Digest

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        _require_sorted_unique(self.used_evidence_ids, "used_evidence_ids")
        _require_sorted_unique(self.used_tools, "used_tools")
        _require_sorted_unique(self.reason_codes, "reason_codes")
        if self.completed_at < self.started_at:
            raise ValueError("Receipt completion cannot precede start")
        if self.status == "completed" and (self.output_sha256 is None or self.reason_codes):
            raise ValueError("completed Receipt requires output and no reasons")
        if self.status != "completed" and (self.output_sha256 is not None or not self.reason_codes):
            raise ValueError("non-completed Receipt requires reasons and no output")
        return self


def _require_sorted_unique(values: Sequence[str], name: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{name} must be sorted and unique")
