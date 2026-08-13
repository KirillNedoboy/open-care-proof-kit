from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from app.agent_trust.builders import build_execution_receipt
from app.agent_trust.canonical import digest_matches, receipt_id, receipt_sha256
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope
from app.family_access.sessions import SessionStore


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class G2Provider(Protocol):
    provider_id: str
    descriptor_hash: str

    def answer(self, disclosure: dict[str, Any], question: str) -> Any: ...


@dataclass(frozen=True)
class EnvelopeProjection:
    """The only envelope data exposed to preparation/provider code."""

    envelope_id: str
    person_id: str
    purpose_id: str
    action_id: str
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
            evidence=tuple(
                {"evidence_id": item.evidence_id, "selected_fields": tuple(item.selected_fields)}
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
        provider_hash: str, fields: list[str], expires_at: datetime,
    ) -> None: ...

    def save_execution_receipt(
        self, receipt: ExecutionReceipt, *, execution_id: str, consent_id: str
    ) -> None: ...

    def get_execution_receipt(
        self, execution_id: str
    ) -> ExecutionReceipt | dict[str, Any] | None: ...


class G2Runtime:
    """Consent gate; authority and context are supplied by narrow callbacks."""

    def __init__(
        self,
        sessions: SessionStore,
        *,
        prepare_envelope: Callable[..., Any],
        revalidate: Callable[..., bool],
        provider: G2Provider,
        repository: G2Repository | None = None,
        project: Callable[[EnvelopeProjection, str], dict[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.sessions, self.prepare_envelope, self.revalidate = (
            sessions,
            prepare_envelope,
            revalidate,
        )
        self.repository = repository
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
        self._receipts: dict[str, ExecutionReceipt] = {}

    def prepare(
        self, session_token: str, question: str, *, purpose_id: str, action_id: str
    ) -> PrepareResult:
        session = self.sessions.resolve(session_token)
        if session is None or not session.active_person_id:
            raise PermissionError("session_or_person_unavailable")
        envelope = self.prepare_envelope(
            actor_id=session.actor_id,
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
            provider_id=self.provider.provider_id,
            provider_hash=self.provider.descriptor_hash,
        )
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
        if session is None or pending is None or pending.session_id != session.session_id:
            raise PermissionError("pending_execution_unavailable")
        consent_id = _hash(json.dumps([
            execution_id, session.actor_id, pending.person_id, pending.purpose_id,
            pending.action_id, pending.envelope_id, pending.provider_id,
            pending.provider_hash, sorted(set(fields)), pending.expires_at.isoformat(),
        ], sort_keys=True))
        consent_fields = sorted(set(fields))
        data: dict[str, object] = {
            "execution_id": execution_id, "consent_id": consent_id,
            "actor_id": session.actor_id, "person_id": pending.person_id,
            "purpose_id": pending.purpose_id, "action_id": pending.action_id,
            "envelope_id": pending.envelope_id, "provider_id": pending.provider_id,
            "provider_hash": pending.provider_hash, "fields": consent_fields,
            "expires_at": pending.expires_at.isoformat(),
        }
        if self.repository is not None and hasattr(self.repository, "save_consent"):
            self.repository.save_consent(
                execution_id=execution_id, consent_id=consent_id,
                actor_id=session.actor_id, person_id=pending.person_id,
                purpose_id=pending.purpose_id, action_id=pending.action_id,
                envelope_id=pending.envelope_id, provider_id=pending.provider_id,
                provider_hash=pending.provider_hash, fields=consent_fields,
                expires_at=pending.expires_at,
            )
        self.sessions.save_consent(data)
        return ConsentResult(execution_id, consent_id, pending.expires_at)

    def execute(self, session_token: str, execution_id: str, question: str) -> ExecuteResult:
        session = self.sessions.resolve(session_token)
        pending = self.sessions.get_pending(execution_id)
        consent = self.sessions.load_consent(execution_id)
        if session is None or pending is None or consent is None:
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        if (
            pending.question_hash != _hash(question)
            or str(consent["expires_at"]) <= self.clock().isoformat()
            or str(consent["envelope_id"]) != pending.envelope_id
            or str(consent["provider_hash"]) != pending.provider_hash
            or str(consent["actor_id"]) != session.actor_id
            or str(consent["person_id"]) != pending.person_id
            or not self.revalidate(pending, session)
        ):
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        envelope = self.prepare_envelope(
            actor_id=session.actor_id,
            person_id=pending.person_id,
            purpose_id=pending.purpose_id,
            action_id=pending.action_id,
            question=question,
        )
        if envelope.envelope_id != pending.envelope_id:
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        consumed = self.sessions.consume_pending(execution_id)
        if consumed is None:
            return ExecuteResult(execution_id, "refused", None, reason_code="replay")
        projection = EnvelopeProjection.from_envelope(envelope)
        disclosure = self.project(projection, question)
        allowed = set(projection.allowed_fields)
        fields = json.loads(str(consent["fields_json"]))
        if not set(fields) <= allowed:
            return ExecuteResult(execution_id, "refused", None, reason_code="tool_not_allowed")
        disclosure["fields"] = fields
        started_at = self.clock()
        answer = self.provider.answer(disclosure, question)
        completed_at = self.clock()
        output = json.dumps(answer, default=str, sort_keys=True, separators=(",", ":")).encode()
        receipt = build_execution_receipt(
            envelope=envelope,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            provider_id=envelope.provider_disclosure.provider_id,
            used_evidence_ids=[item["evidence_id"] for item in projection.evidence],
            used_tools=[],
            output=output,
            reason_codes=[],
        )
        self._receipts[execution_id] = receipt
        if self.repository is not None:
            self.repository.save_execution_receipt(
                receipt, execution_id=execution_id, consent_id=str(consent["consent_id"])
            )
        return ExecuteResult(execution_id, "answered", answer, receipt_id=receipt.receipt_id)

    def get_receipt(
        self, session_token: str, execution_id: str
    ) -> dict[str, object] | ExecutionReceipt | None:
        session = self.sessions.resolve(session_token)
        if session is None:
            return None
        if self.repository is not None:
            receipt = self.repository.get_execution_receipt(execution_id)
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
