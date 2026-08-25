from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from app.agent.providers.contract import (
    AgentProvider,
    ProviderUnavailableError,
    build_provider_execution_request,
)
from app.agent.validation import ValidationResult
from app.agent_trust.builders import BuildRefused, build_execution_receipt
from app.agent_trust.canonical import (
    canonical_bytes,
    digest_matches,
    receipt_id,
    receipt_sha256,
    sha256_hex,
)
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope
from app.family_access.policy import POLICY_VERSION
from app.family_access.sessions import SessionStore


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _bound_provider_identity(disclosure: object) -> tuple[str | None, str | None]:
    """Provider identity bound in a disclosure: descriptor first, legacy field second."""
    descriptor = getattr(disclosure, "provider_descriptor", None)
    if descriptor is not None:
        return descriptor.provider_id, descriptor.descriptor_hash
    return getattr(disclosure, "provider_id", None), None


def _receipt_provider_facts(
    envelope: TrustEnvelope,
) -> tuple[str | None, str | None, str | None, bool | None]:
    """Receipt identity facts: provider_id, model_id, provider_kind, external."""
    descriptor = getattr(envelope.provider_disclosure, "provider_descriptor", None)
    if descriptor is not None:
        return (
            descriptor.provider_id,
            descriptor.model_id,
            descriptor.provider_kind,
            descriptor.external,
        )
    return getattr(envelope.provider_disclosure, "provider_id", None), None, None, None


def _validate_provider_answer(
    answer: dict[str, Any], projection: EnvelopeProjection
) -> ValidationResult:
    """Validate provider output against the Envelope before it can be returned.

    Provider output remains UNTRUSTED until this passes: citations must point
    at Envelope source IDs, and no unsafe prescriptive claims, private paths,
    or secret patterns may be present.
    """
    from app.agent.models import AgentAnswer, AgentContext, ContextSource
    from app.agent.validation import validate_answer

    source_ids = sorted(
        {str(source_id) for item in projection.evidence for source_id in item["source_ids"]}
    )
    context = AgentContext(
        source_kind="envelope",
        family_label="",
        sources=[
            ContextSource(source_id=source_id, title="", source_type="envelope")
            for source_id in source_ids
        ],
    )
    try:
        answer_model = AgentAnswer.model_validate({**answer, "status": "answered"})
    except (TypeError, ValueError):
        return ValidationResult(False, "validation_failed")
    return validate_answer(answer_model, context)


@dataclass(frozen=True)
class EnvelopeProjection:
    """The only envelope data exposed to preparation/provider code."""

    envelope_id: str
    person_id: str
    purpose_id: str
    action_id: str
    requested_action: str
    evidence: tuple[dict[str, Any], ...]
    allowed_tools: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    disclosure_constraints: tuple[str, ...]
    prohibited_operations: tuple[str, ...]

    @classmethod
    def from_envelope(cls, envelope: TrustEnvelope) -> EnvelopeProjection:
        return cls(
            envelope_id=envelope.envelope_id,
            person_id=envelope.person_id,
            purpose_id=envelope.purpose_id,
            action_id=envelope.action_id,
            requested_action=envelope.requested_action,
            evidence=tuple(
                {
                    "evidence_id": item.evidence_id,
                    "content_sha256": item.content_sha256,
                    "selected_fields": tuple(item.selected_fields),
                    "source_ids": tuple(item.source_ids),
                }
                for item in envelope.evidence
            ),
            allowed_tools=tuple(envelope.allowed_tools),
            allowed_fields=tuple(envelope.provider_disclosure.allowed_fields),
            disclosure_constraints=tuple(envelope.disclosure_constraints),
            prohibited_operations=tuple(envelope.prohibited_operations),
        )


class EnvelopeToolMediator:
    """Fail-closed mediator for the envelope's read-only tools."""

    READ_TOOLS = frozenset({"context.read", "source.read"})

    def __init__(self, envelope: TrustEnvelope) -> None:
        self.projection = EnvelopeProjection.from_envelope(envelope)

    def invoke(self, tool: str, *, operation: str = "read") -> dict[str, Any]:
        if operation != "read" or tool not in self.READ_TOOLS:
            raise PermissionError("tool_not_allowed")
        if tool not in self.projection.allowed_tools:
            raise PermissionError("tool_not_allowed")
        if tool == "context.read":
            return {
                "person_id": self.projection.person_id,
                "purpose_id": self.projection.purpose_id,
            }
        return {"evidence": [dict(item) for item in self.projection.evidence]}


@dataclass(frozen=True)
class PrepareResult:
    execution_id: str
    envelope_id: str
    question_hash: str
    preview: dict[str, Any]
    expires_at: datetime


@dataclass(frozen=True)
class ConsentResult:
    execution_id: str
    consent_id: str
    expires_at: datetime


@dataclass(frozen=True)
class ExecuteResult:
    execution_id: str
    status: str
    answer: Any
    receipt_id: str | None = None
    reason_code: str | None = None


class G2Repository(Protocol):
    def save_consent(
        self, *, execution_id: str, consent_id: str, actor_id: str, person_id: str,
        purpose_id: str, action_id: str, envelope_id: str, provider_id: str,
        provider_hash: str, fields: list[str], policy_version: str,
        consented_at: datetime, expires_at: datetime, consent_hash: str,
    ) -> None: ...

    def save_execution_receipt(
        self, receipt: ExecutionReceipt, *, execution_id: str, consent_id: str,
        actor_id: str, person_id: str, mutation_attempted: bool,
    ) -> None: ...

    def get_execution_receipt(
        self, execution_id: str, *, actor_id: str, person_id: str
    ) -> ExecutionReceipt | dict[str, Any] | None: ...



class G2Runtime:
    """Consent gate; authority and context are supplied by narrow callbacks."""

    def __init__(
        self,
        sessions: SessionStore,
        *,
        prepare_envelope: Callable[..., Any],
        revalidate: Callable[..., bool],
        provider: AgentProvider,
        repository: G2Repository | None = None,
        project: Callable[[EnvelopeProjection, str], dict[str, Any]] | None = None,
        resolve_evidence: Callable[[TrustEnvelope], tuple[dict[str, Any], ...]] | None = None,
        authorize_receipt: Callable[[str, str, str], bool] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.sessions, self.prepare_envelope, self.revalidate = (
            sessions,
            prepare_envelope,
            revalidate,
        )
        self.repository = repository
        self.resolve_evidence = resolve_evidence or (
            lambda envelope: tuple(
                {
                    "evidence_id": item.evidence_id,
                    "content_sha256": item.content_sha256,
                    "selected_fields": tuple(item.selected_fields),
                    "source_ids": tuple(item.source_ids),
                }
                for item in envelope.evidence
            )
        )
        self.authorize_receipt = authorize_receipt or (lambda _actor, _credential, _person: True)
        self.provider, self.project = (
            provider,
            project
            or (
                lambda projection, question: {
                    "envelope_id": projection.envelope_id,
                    "purpose_id": projection.purpose_id,
                    "action_id": projection.action_id,
                }
            ),
        )
        self.clock = clock or (lambda: datetime.now(UTC))
        self._consents: dict[str, dict[str, object]] = {}
        self._receipts: dict[str, ExecutionReceipt] = {}
        self._envelopes: dict[str, TrustEnvelope] = {}

    def prepare(
        self, session_token: str, question: str, *, purpose_id: str, action_id: str
    ) -> PrepareResult:
        session = self.sessions.resolve(session_token)
        if session is None or not session.active_person_id:
            raise PermissionError("session_or_person_unavailable")
        envelope = self.prepare_envelope(
            actor_id=session.actor_id,
            credential_id=session.credential_id,
            person_id=session.active_person_id,
            purpose_id=purpose_id,
            action_id=action_id,
            question=question,
        )
        pending = self.sessions.create_pending(
            session_id=session.session_id,
            actor_id=session.actor_id,
            person_id=session.active_person_id,
            purpose_id=purpose_id,
            action_id=action_id,
            question_hash=_hash(question),
            envelope_id=envelope.envelope_id,
            provider_id=self.provider.descriptor.provider_id,
            provider_hash=self.provider.descriptor.descriptor_hash,
        )
        self._envelopes[pending.execution_id] = envelope
        return PrepareResult(
            pending.execution_id,
            envelope.envelope_id,
            pending.question_hash,
            self.project(EnvelopeProjection.from_envelope(envelope), question),
            pending.expires_at,
        )

    def grant_disclosure_consent(
        self, session_token: str, execution_id: str, *, fields: list[str]
    ) -> ConsentResult:
        session = self.sessions.resolve(session_token)
        pending = self.sessions.get_pending(execution_id)
        if (
            session is None
            or pending is None
            or pending.session_id != session.session_id
            or session.active_person_id != pending.person_id
            or not self.revalidate(pending, session)
        ):
            raise PermissionError("pending_execution_unavailable")
        envelope = self._envelopes.get(execution_id)
        if envelope is None:
            envelope = self.prepare_envelope(
                actor_id=session.actor_id, credential_id=session.credential_id,
                person_id=pending.person_id,
                purpose_id=pending.purpose_id, action_id=pending.action_id,
                question="",
            )
        projection = EnvelopeProjection.from_envelope(envelope)
        consent_fields = sorted(set(fields))
        bound_provider_id, bound_provider_hash = _bound_provider_identity(
            envelope.provider_disclosure
        )
        if (
            envelope.envelope_id != pending.envelope_id
            or getattr(envelope, "actor_id", session.actor_id) != session.actor_id
            or getattr(envelope, "person_id", pending.person_id) != pending.person_id
            or getattr(envelope, "purpose_id", pending.purpose_id) != pending.purpose_id
            or getattr(envelope, "action_id", pending.action_id) != pending.action_id
            or (
                bound_provider_id is not None
                and bound_provider_id != pending.provider_id
            )
            or (
                bound_provider_hash is not None
                and bound_provider_hash != pending.provider_hash
            )
            or consent_fields != sorted(projection.allowed_fields)
            or getattr(envelope, "expires_at", pending.expires_at) <= self.clock()
        ):
            raise PermissionError("consent_contract_changed")
        consented_at = self.clock()
        expires_at = getattr(envelope, "expires_at", pending.expires_at)
        policy_version = POLICY_VERSION
        contract = {
            "execution_id": execution_id, "actor_id": session.actor_id,
            "person_id": pending.person_id, "purpose_id": pending.purpose_id,
            "action_id": pending.action_id, "envelope_id": pending.envelope_id,
            "provider_id": pending.provider_id, "provider_hash": pending.provider_hash,
            "fields": consent_fields, "policy_version": policy_version,
            "consented_at": consented_at, "expires_at": expires_at,
        }
        consent_hash = sha256_hex(canonical_bytes(contract))
        consent_id = f"sha256:{consent_hash}"
        data: dict[str, object] = {**contract, "consent_id": consent_id,
                                   "consent_hash": consent_hash}
        self._consents[execution_id] = data
        if self.repository is not None:
            self.repository.save_consent(
                execution_id=execution_id, consent_id=consent_id,
                actor_id=session.actor_id, person_id=pending.person_id,
                purpose_id=pending.purpose_id, action_id=pending.action_id,
                envelope_id=pending.envelope_id, provider_id=pending.provider_id,
                provider_hash=pending.provider_hash, fields=consent_fields,
                policy_version=policy_version, consented_at=consented_at,
                expires_at=expires_at, consent_hash=consent_hash,
            )
        return ConsentResult(execution_id, consent_id, expires_at)

    def execute(self, session_token: str, execution_id: str, question: str) -> ExecuteResult:
        session = self.sessions.resolve(session_token)
        pending = self.sessions.get_pending(execution_id)
        consent = self._consents.get(execution_id)
        if session is None or pending is None or consent is None:
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        if (
            pending.question_hash != _hash(question)
            or (
                (consent["expires_at"] if isinstance(consent["expires_at"], datetime)
                 else datetime.fromisoformat(str(consent["expires_at"])))
                <= self.clock()
            )
            or str(consent["envelope_id"]) != pending.envelope_id
            or str(consent["provider_hash"]) != pending.provider_hash
            or str(consent["actor_id"]) != session.actor_id
            or str(consent["person_id"]) != pending.person_id
            or not self.revalidate(pending, session)
        ):
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        envelope = self._envelopes.get(execution_id)
        if envelope is None:
            envelope = self.prepare_envelope(
                actor_id=session.actor_id, credential_id=session.credential_id,
                person_id=pending.person_id,
                purpose_id=pending.purpose_id, action_id=pending.action_id,
                question=question,
            )
        envelope_expires_at = getattr(envelope, "expires_at", consent["expires_at"])
        _, bound_provider_hash = _bound_provider_identity(envelope.provider_disclosure)
        if (
            envelope.envelope_id != pending.envelope_id
            or (
                bound_provider_hash is not None
                and (
                    bound_provider_hash != pending.provider_hash
                    or bound_provider_hash != self.provider.descriptor.descriptor_hash
                )
            )
            or envelope_expires_at != consent["expires_at"]
        ):
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        consumed = self.sessions.consume_pending(execution_id)
        if consumed is None:
            return ExecuteResult(execution_id, "refused", None, reason_code="replay")
        projection = EnvelopeProjection.from_envelope(envelope)
        fields = list(cast(list[str], consent["fields"]))
        if fields != sorted(projection.allowed_fields):
            return ExecuteResult(execution_id, "refused", None, reason_code="tool_not_allowed")
        started_at = self.clock()
        provider_id, model_id, provider_kind, external = _receipt_provider_facts(envelope)
        try:
            resolved_evidence = self.resolve_evidence(envelope)
            request = build_provider_execution_request(
                projection, question, evidence=resolved_evidence
            )
            result = self.provider.execute(request)
            if result.failure is not None:
                raise ProviderUnavailableError(result.failure.message)
            if result.answer is None:
                raise ProviderUnavailableError("Provider returned no answer.")
        except BuildRefused as refused:
            completed_at = self.clock()
            reasons = refused.reason_codes or ["context_changed"]
            receipt = build_execution_receipt(
                envelope=envelope, started_at=started_at, completed_at=completed_at,
                status="refused", provider_id=provider_id, model_id=model_id,
                provider_kind=provider_kind, external=external,
                used_evidence_ids=[item["evidence_id"] for item in projection.evidence],
                used_tools=[], output=None, reason_codes=reasons,
            )
            self._receipts[execution_id] = receipt
            if self.repository is not None:
                self.repository.save_execution_receipt(
                    receipt, execution_id=execution_id, consent_id=str(consent["consent_id"]),
                    actor_id=session.actor_id, person_id=pending.person_id,
                    mutation_attempted=False,
                )
            return ExecuteResult(execution_id, "refused", None,
                                 reason_code=reasons[0], receipt_id=receipt.receipt_id)
        except Exception:
            completed_at = self.clock()
            receipt = build_execution_receipt(
                envelope=envelope, started_at=started_at, completed_at=completed_at,
                status="failed",
                provider_id=provider_id, model_id=model_id,
                provider_kind=provider_kind, external=external,
                used_evidence_ids=[item["evidence_id"] for item in projection.evidence],
                used_tools=[], output=None, reason_codes=["provider_failed"],
            )
            self._receipts[execution_id] = receipt
            if self.repository is not None:
                self.repository.save_execution_receipt(
                    receipt, execution_id=execution_id, consent_id=str(consent["consent_id"]),
                    actor_id=session.actor_id, person_id=pending.person_id,
                    mutation_attempted=False,
                )
            return ExecuteResult(execution_id, "refused", None,
                                 reason_code="provider_failed", receipt_id=receipt.receipt_id)
        mediator = EnvelopeToolMediator(envelope)
        used_tools: list[str] = []
        mutation_attempted = False
        tool_results: list[dict[str, Any]] = []
        for call in result.tool_calls:
            tool = call.tool
            operation = call.operation
            if operation != "read" or tool not in mediator.READ_TOOLS:
                mutation_attempted = True
                break
            try:
                tool_results.append(mediator.invoke(tool, operation=operation))
            except PermissionError:
                mutation_attempted = True
                break
            used_tools.append(tool)
        if mutation_attempted:
            answer: dict[str, Any] | None = None
            status = "refused"
            reasons = ["tool_not_allowed"]
            output = None
        else:
            validation = _validate_provider_answer(result.answer, projection)
            if not validation.valid:
                answer = None
                status = "refused"
                reasons = [validation.reason_code or "validation_failed"]
                output = None
            else:
                answer = result.answer
                if tool_results:
                    answer = {**answer, "tool_results": tool_results}
                status = "completed"
                reasons = []
                output = json.dumps(answer, default=str, sort_keys=True,
                                    separators=(",", ":")).encode()
        completed_at = self.clock()
        receipt = build_execution_receipt(
            envelope=envelope,
            started_at=started_at,
            completed_at=completed_at,
            provider_id=provider_id, model_id=model_id,
            provider_kind=provider_kind, external=external,
            used_evidence_ids=[item["evidence_id"] for item in projection.evidence],
            status=cast(Any, status),
            used_tools=cast(Any, sorted(set(used_tools))),
            output=output,
            reason_codes=reasons,
        )
        self._receipts[execution_id] = receipt
        if self.repository is not None:
            self.repository.save_execution_receipt(
                receipt, execution_id=execution_id, consent_id=str(consent["consent_id"]),
                actor_id=session.actor_id, person_id=pending.person_id,
                mutation_attempted=mutation_attempted,
            )
        if status != "completed":
            return ExecuteResult(execution_id, "refused", None, reason_code=reasons[0],
                                 receipt_id=receipt.receipt_id)
        return ExecuteResult(execution_id, "answered", answer, receipt_id=receipt.receipt_id)

    def get_receipt(
        self, session_token: str, execution_id: str
    ) -> dict[str, object] | ExecutionReceipt | None:
        session = self.sessions.resolve(session_token)
        if session is None:
            return None
        if session.active_person_id is None or not self.authorize_receipt(
            session.actor_id, session.credential_id, session.active_person_id
        ):
            return None
        if self.repository is not None:
            receipt = self.repository.get_execution_receipt(
                execution_id, actor_id=session.actor_id, person_id=session.active_person_id
            )
            if receipt is None:
                return None
            try:
                parsed = (
                    receipt
                    if isinstance(receipt, ExecutionReceipt)
                    else ExecutionReceipt.model_validate(receipt)
                )
                if parsed.receipt_id != receipt_id(parsed) or not digest_matches(
                    parsed.receipt_sha256, receipt_sha256(parsed)
                ):
                    return None
            except (TypeError, ValueError):
                return None
            return parsed
        receipt = self._receipts.get(execution_id)
        return receipt
