"""OpenCare trust adapter for bounded D1 document fact extraction.

The adapter keeps document extraction on the generic G2 path while making the
provider projection narrower than ordinary chat.  The only provider evidence
records are page-number/text pairs from one immutable D1 snapshot.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from app.agent.g2_runtime import EnvelopeProjection
from app.agent.providers.contract import (
    AgentProvider,
    ProviderExecutionRequest,
)
from app.agent.trust_adapter import OpenCareAuthorizationAdapter
from app.agent_trust.builders import (
    BuildRefused,
    EnvelopeRequest,
    TrustAuthority,
    TrustedEnvelopeBuilder,
)
from app.agent_trust.canonical import canonical_bytes, sha256_hex
from app.agent_trust.identifiers import ACTION_REQUIREMENTS
from app.agent_trust.models import (
    AuthorizationDecision,
    EvidenceItem,
    ProviderDescriptorContract,
    SafetyDecision,
    TrustEnvelope,
)
from app.family_access.service import FamilyAccessService
from app.product_core.document_fact_extraction import (
    CONTRACT_VERSION,
    DOCUMENT_FACT_TYPES,
    DocumentFactAnswerV2,
    _validate_document_fact_answer,
)
from app.product_core.models import DocumentExtractionPage, DocumentExtractionSnapshot, Source
from app.product_core.runtime import ProductCoreRuntime

DOCUMENT_FACT_PURPOSE = "document_fact_extraction"
DOCUMENT_FACT_ACTION = "document.extract_facts"
DOCUMENT_FACT_CONSENT_BASIS = "document-fact-extraction-v1"
DOCUMENT_FACT_REQUEST_PREFIX = "opencare-document-facts-request:"
FACT_TYPES = DOCUMENT_FACT_TYPES


def encode_document_fact_question(
    *,
    person_id: str,
    source_id: str,
    extraction_id: str,
    input_text_hash: str,
    allowed_fact_types: Sequence[str],
    page_count: int,
    character_count: int,
) -> str:
    """Create the internal pending-question binding.

    This value is hashed into SessionStore pending state, but the trust adapter
    deliberately replaces it with a fixed extraction instruction before it
    reaches a provider.
    """

    payload = {
        "person_id": person_id,
        "source_id": source_id,
        "extraction_id": extraction_id,
        "input_text_hash": input_text_hash,
        "allowed_fact_types": sorted(set(allowed_fact_types)),
        "page_count": page_count,
        "character_count": character_count,
    }
    return DOCUMENT_FACT_REQUEST_PREFIX + json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def decode_document_fact_question(question: str) -> dict[str, Any]:
    if not question.startswith(DOCUMENT_FACT_REQUEST_PREFIX):
        raise BuildRefused(["document_binding_invalid"])
    try:
        payload = json.loads(question[len(DOCUMENT_FACT_REQUEST_PREFIX) :])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BuildRefused(["document_binding_invalid"]) from exc
    if not isinstance(payload, dict):
        raise BuildRefused(["document_binding_invalid"])
    expected = {
        "person_id",
        "source_id",
        "extraction_id",
        "input_text_hash",
        "allowed_fact_types",
        "page_count",
        "character_count",
    }
    if set(payload) != expected:
        raise BuildRefused(["document_binding_invalid"])
    if (
        not all(isinstance(payload[key], str) and str(payload[key]).strip() for key in (
            "person_id",
            "source_id",
            "extraction_id",
        ))
        or not isinstance(payload["input_text_hash"], str)
        or len(str(payload["input_text_hash"])) != 64
        or str(payload["input_text_hash"]) != str(payload["input_text_hash"]).lower()
        or any(char not in "0123456789abcdef" for char in str(payload["input_text_hash"]))
        or type(payload["page_count"]) is not int
        or type(payload["character_count"]) is not int
        or payload["page_count"] < 1
        or payload["page_count"] > 200
        or payload["character_count"] < 0
        or payload["character_count"] > 1_000_000
    ):
        raise BuildRefused(["document_binding_invalid"])
    fact_types = payload["allowed_fact_types"]
    if (
        not isinstance(fact_types, list)
        or not fact_types
        or not all(isinstance(item, str) and item in FACT_TYPES for item in fact_types)
        or fact_types != sorted(set(fact_types))
    ):
        raise BuildRefused(["document_binding_invalid"])
    return payload


def document_fact_request_fingerprint(
    *,
    person_id: str,
    source_id: str,
    extraction_id: str,
    input_text_hash: str,
    provider_descriptor_hash: str,
    allowed_fact_types: Sequence[str],
    contract_version: str = CONTRACT_VERSION,
) -> str:
    value = [
        person_id,
        source_id,
        extraction_id,
        input_text_hash,
        contract_version,
        provider_descriptor_hash,
        sorted(set(allowed_fact_types)),
    ]
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def document_snapshot_hash(pages: Sequence[DocumentExtractionPage]) -> str:
    records = [
        {"page_number": int(page.page_number), "text": str(page.normalized_text)}
        for page in sorted(pages, key=lambda item: item.page_number)
    ]
    return sha256_hex(canonical_bytes(cast(Any, records)))


def _d1_text_hash(pages: Sequence[DocumentExtractionPage]) -> str:
    """Match D1's length-delimited text hash for snapshot revalidation."""
    digest = hashlib.sha256()
    for page in sorted(pages, key=lambda item: item.page_number):
        encoded = page.normalized_text.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


@dataclass(frozen=True)
class DocumentSnapshot:
    source: Source
    extraction: DocumentExtractionSnapshot
    pages: tuple[DocumentExtractionPage, ...]
    input_text_hash: str


class _DocumentFactAuthority(TrustAuthority):
    def __init__(self, adapter: DocumentFactTrustAdapter, spec: dict[str, Any]) -> None:
        self.adapter = adapter
        self.spec = spec

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        return self.adapter.authorization.authorize(
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
        if set(required_scopes) != {"document.read"}:
            raise BuildRefused(["evidence_scope_invalid"])
        expected_id = self.adapter.evidence_id(self.spec)
        if list(evidence_ids) != [expected_id] or person_id != self.spec["person_id"]:
            raise BuildRefused(["provenance_missing"])
        snapshot = self.adapter.load_snapshot(self.spec)
        return [
            EvidenceItem(
                evidence_id=expected_id,
                evidence_type="document_text_snapshot",
                person_id=person_id,
                resource_scope="document.read",
                content_sha256=snapshot.input_text_hash,
                source_ids=[str(self.spec["source_id"])],
                provenance_status="source_backed",
                selected_fields=list(self.spec["allowed_fact_types"]),
                observed_at=observed_at.astimezone(UTC),
            )
        ]

    def safety_decision(self, request: EnvelopeRequest, evaluated_at: datetime) -> SafetyDecision:
        del request
        return SafetyDecision(
            decision="allow",
            reason_codes=[],
            policy_version="document-facts-safety-v1",
            evaluated_at=evaluated_at,
            limitations=sorted(
                [
                    "Only the selected D1 document text snapshot is available.",
                    "Extracted facts remain pending until human review.",
                ]
            ),
            required_notices=[
                "No diagnosis, treatment, dosage, or medication start/stop advice is provided."
            ],
        )

    def validate_disclosure(self, request: EnvelopeRequest) -> None:
        if request.disclosure_mode == "external_provider" and not request.provider_descriptor:
            raise BuildRefused(["provider_disclosure_denied"])


class DocumentFactTrustAdapter:
    """Bind one D1 snapshot to a genuine G2 Envelope and provider projection."""

    def __init__(
        self,
        runtime: ProductCoreRuntime,
        family_service: FamilyAccessService,
        provider: AgentProvider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.runtime = runtime
        self.family_service = family_service
        self.authorization = OpenCareAuthorizationAdapter(family_service)
        self.provider = provider
        self.clock = clock or runtime.clock

    def set_provider(self, provider: AgentProvider) -> None:
        self.provider = provider

    @staticmethod
    def evidence_id(spec: dict[str, Any]) -> str:
        return f"document-facts:{spec['source_id']}:{spec['extraction_id']}"

    def load_snapshot(self, spec: dict[str, Any]) -> DocumentSnapshot:
        with self.runtime.database.uow() as uow:
            source = uow.sources.get(str(spec["source_id"]))
            extraction = uow.document_extractions.get(str(spec["extraction_id"]))
            if (
                source is None
                or extraction is None
                or source.person_id != str(spec["person_id"])
                or source.source_type != "document"
                or extraction.source_id != source.id
                or extraction.person_id != source.person_id
                or extraction.status != "complete"
            ):
                raise BuildRefused(["document_binding_invalid"])
            pages = tuple(uow.document_extractions.list_pages(extraction.extraction_id))
        if (
            len(pages) != extraction.page_count
            or [page.page_number for page in pages] != list(range(1, len(pages) + 1))
            or any(
                page.source_id != source.id
                or page.person_id != source.person_id
                or page.extraction_id != extraction.extraction_id
                or page.extracted_chars != len(page.normalized_text)
                or hashlib.sha256(page.normalized_text.encode("utf-8")).hexdigest()
                != page.page_hash
                for page in pages
            )
            or sum(page.extracted_chars for page in pages) != extraction.total_chars
            or _d1_text_hash(pages) != extraction.text_hash
        ):
            raise BuildRefused(["document_binding_invalid"])
        input_hash = document_snapshot_hash(pages)
        if input_hash != str(spec["input_text_hash"]):
            raise BuildRefused(["context_changed"])
        return DocumentSnapshot(source, extraction, pages, input_hash)

    def build_envelope(self, **kwargs: Any) -> TrustEnvelope:
        spec = decode_document_fact_question(str(kwargs["question"]))
        if str(kwargs["person_id"]) != spec["person_id"]:
            raise BuildRefused(["person_mismatch"])
        self.load_snapshot(spec)
        descriptor = self.provider.descriptor
        descriptor_contract = ProviderDescriptorContract(
            provider_id=descriptor.provider_id,
            model_id=descriptor.model_id,
            provider_kind=descriptor.provider_kind,
            endpoint_class=descriptor.endpoint_class,
            external=descriptor.external,
            descriptor_hash=descriptor.descriptor_hash,
        )
        authority = _DocumentFactAuthority(self, spec)
        request = EnvelopeRequest(
            actor_id=str(kwargs["actor_id"]),
            credential_id=str(kwargs["credential_id"]),
            person_id=str(kwargs["person_id"]),
            purpose_id=cast(Literal["document_fact_extraction"], DOCUMENT_FACT_PURPOSE),
            action_id=cast(Literal["document.extract_facts"], DOCUMENT_FACT_ACTION),
            requested_action=(
                "Extract source-stated document facts without diagnosis or treatment advice."
            ),
            requested_tools=["source.read"],
            evidence_ids=[self.evidence_id(spec)],
            disclosure_mode=(
                "external_provider" if descriptor.external else "local_only"
            ),
            provider_id=descriptor.provider_id,
            provider_descriptor=descriptor_contract,
            consent_basis_id=DOCUMENT_FACT_CONSENT_BASIS,
            ttl_seconds=300,
        )
        return TrustedEnvelopeBuilder(authority, clock=self.clock).build(request)

    def resolve_evidence(self, envelope: TrustEnvelope) -> tuple[dict[str, Any], ...]:
        if len(envelope.evidence) != 1:
            raise BuildRefused(["context_changed"])
        evidence = envelope.evidence[0]
        if len(evidence.source_ids) != 1 or not evidence.evidence_id.startswith("document-facts:"):
            raise BuildRefused(["context_changed"])
        source_id = evidence.source_ids[0]
        encoded = evidence.evidence_id.removeprefix("document-facts:")
        if not encoded.startswith(f"{source_id}:"):
            raise BuildRefused(["context_changed"])
        extraction_id = encoded[len(source_id) + 1 :]
        spec = {
            "person_id": envelope.person_id,
            "source_id": source_id,
            "extraction_id": extraction_id,
            "input_text_hash": evidence.content_sha256,
            "allowed_fact_types": list(evidence.selected_fields),
            "page_count": 1,
            "character_count": 0,
        }
        snapshot = self.load_snapshot(spec)
        return tuple(
            {"page_number": int(page.page_number), "text": page.normalized_text}
            for page in snapshot.pages
        )

    def provider_request_builder(
        self,
        projection: EnvelopeProjection,
        question: str,
        evidence: tuple[dict[str, Any], ...],
    ) -> ProviderExecutionRequest:
        del question
        records: list[dict[str, Any]] = []
        for item in evidence:
            if set(item) != {"page_number", "text"}:
                raise BuildRefused(["provider_projection_invalid"])
            if type(item["page_number"]) is not int or not isinstance(item["text"], str):
                raise BuildRefused(["provider_projection_invalid"])
            records.append({"page_number": item["page_number"], "text": item["text"]})
        allowed_fact_types = tuple(
            sorted(set(projection.allowed_fields) & FACT_TYPES)
        )
        if not allowed_fact_types:
            raise BuildRefused(["fact_type_not_allowed"])
        return ProviderExecutionRequest(
            question=(
                "Extract only explicit medication, condition, lab, procedure, "
                "recommendation, and follow-up facts from these pages."
            ),
            purpose_id=projection.purpose_id,
            action_id=projection.action_id,
            requested_action=(
                "Extract source-stated document facts without diagnosis or treatment advice."
            ),
            evidence=tuple(records),
            allowed_tools=tuple(projection.allowed_tools),
            allowed_fields=allowed_fact_types,
            output_contract=DocumentFactAnswerV2.model_json_schema(),
            system_instructions=(
                "Extract only statements directly supported by the supplied document text. "
                "Never diagnose. Never recommend treatment yourself. Never infer procedures, "
                "follow-ups, or clinical intent. Preserve source wording. Classify each "
                "semantic fact once using priority rules: medication instructions stay "
                "medication; a merely suggested procedure is a recommendation; an explicitly "
                "performed, occurring, or scheduled named procedure is a procedure; an "
                "explicit future recheck, repeat, or return with timing intent is a "
                "follow_up; other explicit advice or instructions are recommendations. "
                "Every fact requires its exact page and one verbatim evidence quote. Omit "
                "uncertain facts. Do not correct medical terminology. Do not derive dates. "
                "Do not convert units. Do not interpret labs."
            ),
            disclosure_constraints=tuple(projection.disclosure_constraints),
            prohibited_operations=tuple(projection.prohibited_operations),
        )

    @staticmethod
    def answer_validator(
        answer: dict[str, Any], projection: EnvelopeProjection
    ) -> Any:
        return _validate_document_fact_answer(
            answer, allowed_fact_types=projection.allowed_fields
        )

    def project(self, projection: EnvelopeProjection, question: str) -> dict[str, Any]:
        spec = decode_document_fact_question(question)
        snapshot = self.load_snapshot(spec)
        descriptor = self.provider.descriptor
        return {
            "provider_id": descriptor.provider_id,
            "model_id": descriptor.model_id,
            "provider_kind": descriptor.provider_kind,
            "external": descriptor.external,
            "retention": "provider_policy" if descriptor.external else "request_only",
            "safe_filename": snapshot.source.original_filename or "document",
            "filename": snapshot.source.original_filename or "document",
            "page_count": snapshot.extraction.page_count,
            "character_count": snapshot.extraction.total_chars,
            "enabled_categories": list(spec["allowed_fact_types"]),
            "fields": list(spec["allowed_fact_types"]),
            "evidence_count": len(projection.evidence),
            "disclosure_constraints": list(projection.disclosure_constraints),
        }

    def current_allowed_fact_types(self, actor_id: str, person_id: str) -> list[str]:
        allowed: list[str] = []
        with self.runtime.database.uow() as uow:
            assert uow.connection is not None
            for fact_type in sorted(FACT_TYPES):
                decision, candidate = self.family_service._authorize_person_in_connection(
                    uow.connection, actor_id, person_id, f"{fact_type}.write"
                )
                if decision.allowed and candidate is not None:
                    allowed.append(fact_type)
        return sorted(allowed)

    def revalidate(self, pending: Any, session: Any) -> bool:
        if session.active_person_id != pending.person_id or session.actor_id != pending.actor_id:
            return False
        with self.runtime.database.uow() as uow:
            run = uow.document_fact_extractions.get_run_by_execution_id(
                pending.execution_id
            )
        if (
            run is None
            or run.execution_id != pending.execution_id
            or run.person_id != pending.person_id
            or run.actor_id != pending.actor_id
            or run.envelope_id != pending.envelope_id
            or run.provider_id != pending.provider_id
            or run.provider_descriptor_hash != pending.provider_hash
            or run.status not in {"prepared", "consent_required", "consented"}
        ):
            return False
        descriptor = self.provider.descriptor
        if (
            descriptor.provider_id != run.provider_id
            or descriptor.descriptor_hash != run.provider_descriptor_hash
            or descriptor.model_id != run.model_id
            or descriptor.external != run.external
        ):
            return False
        try:
            self.load_snapshot(
                {
                    "person_id": run.person_id,
                    "source_id": run.source_id,
                    "extraction_id": run.extraction_id,
                    "input_text_hash": run.input_text_hash,
                    "allowed_fact_types": list(run.allowed_fact_types),
                    "page_count": 1,
                    "character_count": 0,
                }
            )
        except BuildRefused:
            return False
        current_types = self.current_allowed_fact_types(run.actor_id, run.person_id)
        if current_types != sorted(run.allowed_fact_types):
            return False
        expected_fingerprint = document_fact_request_fingerprint(
            person_id=run.person_id,
            source_id=run.source_id,
            extraction_id=run.extraction_id,
            input_text_hash=run.input_text_hash,
            provider_descriptor_hash=run.provider_descriptor_hash or "",
            allowed_fact_types=run.allowed_fact_types,
            contract_version=run.contract_version,
        )
        if expected_fingerprint != run.request_fingerprint:
            return False
        decision = self.authorization.authorize(
            actor_id=session.actor_id,
            credential_id=session.credential_id,
            person_id=run.person_id,
            required_scopes=ACTION_REQUIREMENTS[DOCUMENT_FACT_ACTION][0],
            authorized_at=self.clock(),
        )
        return decision.decision == "allow" and decision.snapshot is not None

    def authorize_receipt(self, actor_id: str, credential_id: str, person_id: str) -> bool:
        decision = self.authorization.authorize(
            actor_id=actor_id,
            credential_id=credential_id,
            person_id=person_id,
            required_scopes=ACTION_REQUIREMENTS[DOCUMENT_FACT_ACTION][0],
            authorized_at=self.clock(),
        )
        return decision.decision == "allow"
