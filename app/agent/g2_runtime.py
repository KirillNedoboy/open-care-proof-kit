from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from app.agent_trust.builders import build_execution_receipt
from app.family_access.sessions import PendingExecution, SessionStore


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class G2Provider(Protocol):
    provider_id: str
    descriptor_hash: str
    def answer(self, disclosure: dict[str, Any], question: str) -> Any: ...


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


class G2Runtime:
    """Consent gate; authority and context are supplied by narrow callbacks."""
    def __init__(self, sessions: SessionStore, *, prepare_envelope: Callable[..., Any],
                 revalidate: Callable[..., bool], provider: G2Provider,
                 project: Callable[[Any, str], dict[str, Any]] | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.sessions, self.prepare_envelope, self.revalidate = sessions, prepare_envelope, revalidate
        self.provider, self.project = provider, project or (lambda envelope, question: {"envelope_id": envelope.envelope_id})
        self.clock = clock or (lambda: datetime.now(UTC))
        self._consents: dict[str, dict[str, Any]] = {}

    def prepare(self, session_token: str, question: str, *, purpose_id: str, action_id: str) -> PrepareResult:
        session = self.sessions.resolve(session_token)
        if session is None or not session.active_person_id:
            raise PermissionError("session_or_person_unavailable")
        envelope = self.prepare_envelope(actor_id=session.actor_id, person_id=session.active_person_id,
                                         purpose_id=purpose_id, action_id=action_id, question=question)
        pending = self.sessions.create_pending(session_id=session.session_id, actor_id=session.actor_id,
            person_id=session.active_person_id, question_hash=_hash(question), envelope_id=envelope.envelope_id,
            provider_id=self.provider.provider_id, provider_hash=self.provider.descriptor_hash)
        return PrepareResult(pending.execution_id, envelope.envelope_id, pending.question_hash,
                             self.project(envelope, question), pending.expires_at)

    def grant_disclosure_consent(self, session_token: str, execution_id: str, *, fields: list[str]) -> ConsentResult:
        session = self.sessions.resolve(session_token); pending = self.sessions.get_pending(execution_id)
        if session is None or pending is None or pending.session_id != session.session_id:
            raise PermissionError("pending_execution_unavailable")
        consent_id = _hash(json.dumps([execution_id, session.actor_id, pending.person_id,
                                        pending.envelope_id, pending.provider_id,
                                        pending.provider_hash, sorted(fields)]))
        self._consents[execution_id] = {
            "consent_id": consent_id, "fields": tuple(sorted(set(fields))),
            "envelope_id": pending.envelope_id, "provider_id": pending.provider_id,
            "provider_hash": pending.provider_hash, "expires_at": pending.expires_at,
        }
        return ConsentResult(execution_id, consent_id, pending.expires_at)

    def execute(self, session_token: str, execution_id: str, question: str) -> ExecuteResult:
        session = self.sessions.resolve(session_token)
        pending = self.sessions.get_pending(execution_id)
        consent = self._consents.get(execution_id)
        if session is None or pending is None or consent is None or pending.session_id != session.session_id:
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        if (pending.question_hash != _hash(question)
                or consent["expires_at"] <= self.clock()
                or consent["envelope_id"] != pending.envelope_id
                or consent["provider_hash"] != pending.provider_hash
                or not self.revalidate(pending, session)):
            return ExecuteResult(execution_id, "refused", None, reason_code="context_changed")
        consumed = self.sessions.consume_pending(execution_id)
        if consumed is None:
            return ExecuteResult(execution_id, "refused", None, reason_code="replay")
        envelope = self.prepare_envelope(actor_id=session.actor_id, person_id=session.active_person_id,
                                         purpose_id="", action_id="", question=question)
        disclosure = self.project(envelope, question)
        disclosure["fields"] = list(consent["fields"])
        answer = self.provider.answer(disclosure, question)
        receipt_id = "sha256:" + _hash(execution_id + json.dumps(answer, default=str, sort_keys=True))
        return ExecuteResult(execution_id, "answered", answer, receipt_id=receipt_id)
