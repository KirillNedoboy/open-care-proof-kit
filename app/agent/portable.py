from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agent.models import AgentAnswer, AgentContext, Citation, ContextItem, ContextSource
from app.agent.policy import classify_question
from app.agent.validation import ValidationResult, validate_answer


class PortableContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    category: str
    text: str
    evidence_status: Literal["source_backed", "recorded_without_source", "unknown"]
    source_ids: list[str] = Field(default_factory=list)


class PortableSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    source_type: str


class PortableHealthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    vault_mode: str
    people: list[str] = Field(default_factory=list)
    relationships: list[PortableContextItem] = Field(default_factory=list)
    medications: list[PortableContextItem] = Field(default_factory=list)
    labs: list[PortableContextItem] = Field(default_factory=list)
    visits: list[PortableContextItem] = Field(default_factory=list)
    timeline: list[PortableContextItem] = Field(default_factory=list)
    recorded_questions: list[PortableContextItem] = Field(default_factory=list)
    sources: list[PortableSource] = Field(default_factory=list)
    context_items: list[PortableContextItem] = Field(default_factory=list)


ANSWER_FIELDS = {
    "status",
    "answer",
    "citations",
    "unknowns",
    "doctor_questions",
    "boundary_notices",
    "evidence_claims",
}


class PortableEvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_item_id: str
    source_id: str
    evidence_text: str


class PortableAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "refused", "validation_failed"]
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    doctor_questions: list[str] = Field(default_factory=list)
    boundary_notices: list[str] = Field(default_factory=list)
    evidence_claims: list[PortableEvidenceClaim] = Field(default_factory=list)


def export_portable_context(
    context: AgentContext,
    *,
    generated_at: datetime | None = None,
) -> PortableHealthContext:
    items = [_portable_item(item) for item in context.items]
    return PortableHealthContext(
        generated_at=generated_at or datetime.now(UTC),
        vault_mode=context.source_kind,
        people=list(context.people),
        relationships=[item for item in items if item.category == "relationship"],
        medications=[item for item in items if item.category == "medication"],
        labs=[item for item in items if item.category == "lab"],
        visits=[item for item in items if item.category == "visit"],
        timeline=[item for item in items if item.category == "timeline"],
        recorded_questions=[item for item in items if item.category == "recorded_question"],
        sources=[
            PortableSource(
                source_id=source.source_id,
                title=source.title,
                source_type=source.source_type,
            )
            for source in context.sources
        ],
        context_items=items,
    )


def context_to_agent_context(context: PortableHealthContext) -> AgentContext:
    return AgentContext(
        source_kind=context.vault_mode,
        family_label="Portable OpenCare context",
        people=list(context.people),
        items=[
            ContextItem(
                id=item.item_id,
                kind=item.category,
                text=item.text,
                source_ids=list(item.source_ids),
                provenance_status=item.evidence_status,
            )
            for item in context.context_items
            if item.evidence_status != "unknown"
        ],
        sources=[
            ContextSource(
                source_id=source.source_id,
                title=source.title,
                source_type=source.source_type,
            )
            for source in context.sources
        ],
    )


def parse_portable_answer(payload: Any) -> PortableAnswer:
    if not isinstance(payload, dict) or set(payload) != ANSWER_FIELDS:
        raise ValueError("invalid_answer_schema")
    return PortableAnswer.model_validate(payload)


def validate_portable_answer(
    context: PortableHealthContext,
    answer_payload: Any,
    question: str,
) -> ValidationResult:
    submitted = parse_portable_answer(answer_payload)
    policy = classify_question(question)
    if policy.decision != "allowed":
        if submitted.status != "refused" or submitted.evidence_claims:
            return ValidationResult(False, "policy_response_required")
        return ValidationResult(True)
    if submitted.status != "answered":
        return ValidationResult(False, "unexpected_answer_status")
    items = {item.item_id: item for item in context.context_items}
    claims = submitted.evidence_claims
    if len({claim.context_item_id for claim in claims}) != len(claims):
        return ValidationResult(False, "duplicate_evidence_claim")
    for claim in claims:
        item = items.get(claim.context_item_id)
        if (
            item is None
            or item.evidence_status != "source_backed"
            or claim.source_id not in item.source_ids
            or claim.evidence_text != _normalize_text(item.text)
        ):
            return ValidationResult(False, "invalid_evidence_binding")
    if not claims:
        expected_answer = "No source-backed information is available in the supplied context."
        if not submitted.unknowns or submitted.answer != expected_answer or submitted.citations:
            return ValidationResult(False, "answer_not_canonical")
        return validate_answer(
            AgentAnswer(
                status="answered",
                answer=expected_answer,
                unknowns=submitted.unknowns,
                doctor_questions=submitted.doctor_questions,
                boundary_notices=submitted.boundary_notices,
            ),
            context_to_agent_context(context),
        )
    canonical = "\n".join(claim.evidence_text for claim in claims)
    citations = [
        Citation(source_id=claim.source_id, claim=claim.evidence_text) for claim in claims
    ]
    if submitted.answer != canonical or submitted.citations != citations:
        return ValidationResult(False, "answer_not_canonical")
    return validate_answer(
        AgentAnswer(
            status="answered",
            answer=canonical,
            citations=citations,
            unknowns=submitted.unknowns,
            doctor_questions=submitted.doctor_questions,
            boundary_notices=submitted.boundary_notices,
        ),
        context_to_agent_context(context),
    )


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _portable_item(item: ContextItem) -> PortableContextItem:
    return PortableContextItem(
        item_id=item.id,
        category=item.kind,
        text=item.text,
        evidence_status=item.provenance_status,
        source_ids=list(item.source_ids),
    )
