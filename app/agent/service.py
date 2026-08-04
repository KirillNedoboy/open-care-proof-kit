from time import monotonic
from typing import Any, Protocol

from app.agent.audit import emit_audit
from app.agent.context import build_agent_context
from app.agent.models import AgentAnswer, AgentContext, Citation, ContextItem
from app.agent.policy import classify_question
from app.agent.provider import OpenAIResponsesProvider, ProviderUnavailableError
from app.agent.validation import validate_answer
from app.config import Settings
from app.health_vault.runtime_loader import load_active_vault


class AnswerProvider(Protocol):
    def answer(self, context: object, question: str) -> AgentAnswer | dict[str, Any]: ...


class DemoProvider:
    def answer(self, context: object, question: str) -> AgentAnswer:
        if not isinstance(context, AgentContext):
            raise ValueError("Demo provider requires AgentContext.")
        normalized = question.lower()
        if "doctor" in normalized or "clinician" in normalized:
            return _doctor_questions_answer(context)
        if "changed" in normalized or "latest recorded visit" in normalized:
            return _timeline_answer(context)
        if (
            "source-backed" in normalized
            or "source backed" in normalized
            or "which source" in normalized
        ):
            return _sources_answer(context)
        if "dosage" in normalized or "dose" in normalized:
            return _recorded_dosage_answer(context)
        if "medication" in normalized or "medications" in normalized:
            return _recorded_medications_answer(context)
        if "missing" in normalized:
            return _missing_answer(context)
        return AgentAnswer(
            status="answered",
            answer=(
                "OpenCare can summarize recorded vault context, trace information to sources, "
                "identify missing information, and prepare clinician discussion questions."
            ),
            unknowns=["The requested topic is not available in the deterministic demo prompts."],
            boundary_notices=[
                "OpenCare is source-constrained and policy-checked; it cannot guarantee medical "
                "correctness."
            ],
        )


class GuardedChatService:
    def __init__(
        self,
        *,
        context: AgentContext,
        provider: AnswerProvider,
        provider_mode: str,
    ) -> None:
        self._context = context
        self._provider = provider
        self._provider_mode = provider_mode

    @classmethod
    def for_settings(cls, settings: Settings) -> "GuardedChatService":
        context = build_agent_context(load_active_vault(settings))
        return cls.for_context(context, settings)

    @classmethod
    def for_context(
        cls, context: AgentContext, settings: Settings
    ) -> "GuardedChatService":
        if settings.agent_mode == "demo":
            return cls(context=context, provider=DemoProvider(), provider_mode="demo")
        return cls(
            context=context,
            provider=OpenAIResponsesProvider.from_settings(settings),
            provider_mode="openai_responses",
        )

    def answer(self, question: str) -> AgentAnswer:
        started = monotonic()
        policy = classify_question(question)
        if policy.decision != "allowed":
            answer = AgentAnswer(
                status="refused",
                answer=policy.response_text,
                boundary_notices=[
                    "OpenCare does not provide diagnosis or treatment recommendations."
                ],
            )
            self._audit(question, policy, answer, "not_called", policy.reason_code, started)
            return answer
        try:
            provider_context: object = self._context
            if not isinstance(self._provider, DemoProvider):
                provider_context = self._context.model_dump()
            raw_answer = self._provider.answer(provider_context, question)
            answer = (
                raw_answer
                if isinstance(raw_answer, AgentAnswer)
                else AgentAnswer.model_validate({"status": "answered", **raw_answer})
            )
        except (ProviderUnavailableError, ValueError):
            answer = _validation_failed_answer()
            self._audit(question, policy, answer, "failed", "provider_unavailable", started)
            return answer
        validation = validate_answer(answer, self._context)
        if not validation.valid:
            answer = _validation_failed_answer()
            self._audit(question, policy, answer, "failed", validation.reason_code, started)
            return answer
        self._audit(question, policy, answer, "passed", None, started)
        return answer

    def _audit(
        self,
        question: str,
        policy: object,
        answer: AgentAnswer,
        validation_result: str,
        reason_code: str | None,
        started: float,
    ) -> None:
        from app.agent.models import PolicyDecision

        emit_audit(
            provider_mode=self._provider_mode,
            policy=policy if isinstance(policy, PolicyDecision) else classify_question(question),
            validation_result=validation_result,
            citation_source_ids=[citation.source_id for citation in answer.citations],
            question_length=len(question),
            reason_code=reason_code,
            latency_ms=round((monotonic() - started) * 1000),
        )


def _validation_failed_answer() -> AgentAnswer:
    return AgentAnswer(
        status="validation_failed",
        answer="OpenCare could not validate a source-backed response for this question.",
        unknowns=["No unvalidated provider output was displayed."],
        boundary_notices=[
            "Validation reduces unsupported output but cannot guarantee medical correctness."
        ],
    )


def _first_source(context: AgentContext, preferred_type: str | None = None) -> str:
    for source in context.sources:
        if preferred_type is None or source.source_type == preferred_type:
            return source.source_id
    return context.sources[0].source_id


def _doctor_questions_answer(context: AgentContext) -> AgentAnswer:
    source_id = _first_source(context, "visit_note")
    questions = [item.text for item in context.items if item.kind == "recorded_question"]
    return AgentAnswer(
        status="answered",
        answer="These recorded questions can help prepare a clinician discussion.",
        citations=[
            Citation(
                source_id=source_id,
                claim="The source-backed vault includes clinician discussion context.",
            )
        ],
        doctor_questions=questions,
        boundary_notices=["These are discussion prompts, not treatment instructions."],
    )


def _timeline_answer(context: AgentContext) -> AgentAnswer:
    events = [item for item in context.items if item.kind == "timeline"]
    latest = events[-1] if events else None
    if latest is None:
        return _missing_answer(context)
    return AgentAnswer(
        status="answered",
        answer=f"The latest recorded timeline event is: {latest.text}.",
        citations=[
            Citation(
                source_id=latest.source_ids[0],
                claim="This event is recorded in the vault timeline.",
            )
        ],
        boundary_notices=["This is a recorded timeline summary, not medical interpretation."],
    )


def _sources_answer(context: AgentContext) -> AgentAnswer:
    source_ids = ", ".join(source.source_id for source in context.sources)
    return AgentAnswer(
        status="answered",
        answer="The vault contains source-backed records linked to the listed sources.",
        citations=[
            Citation(
                source_id=source.source_id,
                claim="This source is available for provenance tracing.",
            )
            for source in context.sources
        ],
        unknowns=[
            "Person and relationship labels are recorded context without document source IDs: "
            f"{source_ids}."
        ],
    )


def _recorded_medications_answer(context: AgentContext) -> AgentAnswer:
    medications = [item for item in context.items if item.kind == "medication"]
    citations = _citations_for_items(medications)
    if not citations:
        return AgentAnswer(
            status="answered",
            answer=(
                "No source-backed medication records are available in the current vault context."
            ),
            unknowns=["Medication records are missing a document source in this vault context."],
            boundary_notices=["OpenCare does not recommend, select, or change medications."],
        )
    return AgentAnswer(
        status="answered",
        answer=f"Recorded medications: {'; '.join(item.text for item in medications)}.",
        citations=citations,
        boundary_notices=[
            "This is recorded medication context, not a recommendation or treatment instruction."
        ],
    )


def _recorded_dosage_answer(context: AgentContext) -> AgentAnswer:
    medications = [item for item in context.items if item.kind == "medication"]
    citations = _citations_for_items(medications)
    if not citations:
        return AgentAnswer(
            status="answered",
            answer="No source-backed medication record is available in the current vault context.",
            unknowns=[
                "No medication record is available to establish a source-backed dosage."
            ],
            boundary_notices=["OpenCare does not calculate, recommend, or modify a dosage."],
        )
    return AgentAnswer(
        status="answered",
        answer="No recorded source-backed dosage is available in the current vault context.",
        citations=citations,
        unknowns=[
            "No recorded source-backed dosage is available for the recorded medication context."
        ],
        boundary_notices=["OpenCare does not calculate, recommend, or modify a dosage."],
    )


def _citations_for_items(items: list[ContextItem]) -> list[Citation]:
    source_ids = {
        source_id
        for item in items
        for source_id in item.source_ids
    }
    return [
        Citation(
            source_id=source_id,
            claim="This source records the referenced medication context.",
        )
        for source_id in sorted(source_ids)
    ]


def _missing_answer(context: AgentContext) -> AgentAnswer:
    missing = [
        item.text for item in context.items if item.provenance_status == "recorded_without_source"
    ]
    return AgentAnswer(
        status="answered",
        answer=(
            "The following recorded context does not include a document source ID in this compact "
            "view."
        ),
        citations=[
            Citation(
                source_id=_first_source(context),
                claim="The vault has provenance-aware document sources.",
            )
        ],
        unknowns=missing or ["No missing information was identified in the compact context."],
    )
