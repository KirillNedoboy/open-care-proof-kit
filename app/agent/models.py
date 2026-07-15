from typing import Literal

from pydantic import BaseModel, Field

AnswerStatus = Literal["answered", "refused", "validation_failed"]
PolicyCategory = Literal["allowed", "blocked", "urgent"]


class AgentQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class PolicyDecision(BaseModel):
    decision: PolicyCategory
    reason_code: str
    response_text: str


class ContextItem(BaseModel):
    id: str
    kind: str
    text: str
    source_ids: list[str] = Field(default_factory=list)
    provenance_status: Literal["source_backed", "recorded_without_source"]


class ContextSource(BaseModel):
    source_id: str
    title: str
    source_type: str


class AgentContext(BaseModel):
    source_kind: str
    family_label: str
    people: list[str] = Field(default_factory=list)
    items: list[ContextItem] = Field(default_factory=list)
    sources: list[ContextSource] = Field(default_factory=list)


class Citation(BaseModel):
    source_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)


class AgentAnswer(BaseModel):
    status: AnswerStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    doctor_questions: list[str] = Field(default_factory=list)
    boundary_notices: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    timestamp: str
    request_id: str
    provider_mode: str
    policy_category: PolicyCategory
    policy_decision: str
    validation_result: str
    citation_source_ids: list[str]
    question_length: int
    reason_code: str | None = None
    latency_ms: int | None = None
