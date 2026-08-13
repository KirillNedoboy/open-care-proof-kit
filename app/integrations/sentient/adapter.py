"""Sentient agent framework adapter for the OpenCare G2 demo context.

This module is optional: it imports ``sentient_agent_framework`` and must
never be imported by OpenCare core. Session/request identifiers from the
Sentient framework are correlation-only metadata; they are never used for
authorization and never become OpenCare actor or person identifiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from sentient_agent_framework.interface.agent import AbstractAgent
from sentient_agent_framework.interface.request import Query
from sentient_agent_framework.interface.response_handler import ResponseHandler
from sentient_agent_framework.interface.session import Session

from app.agent.g2_runtime import EnvelopeProjection, G2Provider, G2Runtime
from app.agent.policy import classify_question
from app.agent_trust.builders import BuildRefused
from app.agent_trust.models import ExecutionReceipt

if TYPE_CHECKING:
    from app.integrations.sentient.demo import DemoContext

PURPOSE_ID: Literal["record_explanation"] = "record_explanation"
ACTION_ID: Literal["answer_question"] = "answer_question"


def redacted(receipt: ExecutionReceipt) -> dict[str, str]:
    """Return the only receipt fields safe to surface to a Sentient client."""
    return {
        "receipt_id": receipt.receipt_id,
        "canonical_hash": receipt.receipt_sha256,
        "envelope_hash": receipt.envelope_id,
        "outcome": receipt.status,
        "validation_result": "valid",
    }


def _sources_payload(projection: EnvelopeProjection) -> dict[str, Any]:
    """Envelope-projected sources; never anything outside the Envelope."""
    return {
        "sources": [
            {
                "evidence_id": item["evidence_id"],
                "selected_fields": list(item["selected_fields"]),
            }
            for item in projection.evidence
        ]
    }


class DeterministicDemoProvider(G2Provider):
    """Local deterministic provider; the answer derives only from the disclosure."""

    provider_id: str = "opencare.deterministic.demo"
    descriptor_hash: str = "sha256:opencare-deterministic-demo-v1"

    def answer(self, disclosure: dict[str, Any], question: str) -> dict[str, Any]:
        del question
        evidence = disclosure.get("evidence", [])
        fields = disclosure.get("fields", [])
        if not isinstance(evidence, list) or not isinstance(fields, list):
            raise ValueError("invalid disclosure shape")
        field_text = ", ".join(sorted(str(field) for field in fields)) or "none"
        answer_text = (
            f"Recorded context only: {len(evidence)} evidence item(s) authorized; "
            f"disclosed fields: {field_text}. This is recorded context only; "
            "no diagnosis, treatment, dosage, or medication advice is provided."
        )
        return {
            "answer": answer_text,
            "citations": [],
            "unknowns": [],
            "doctor_questions": [],
            "boundary_notices": [],
        }


async def _refuse(
    response_handler: ResponseHandler,
    *,
    reason_code: str,
    message: str | None = None,
    receipt: ExecutionReceipt | None = None,
) -> None:
    """Emit a bounded refusal; never leaks another Person's existence."""
    await response_handler.emit_json(
        "OPENCARE_STATUS",
        {
            "stage": "refused",
            "purpose": PURPOSE_ID,
            "requested_action": ACTION_ID,
            "reason_code": reason_code,
        },
    )
    await response_handler.emit_error(
        message or "OpenCare refused this request under its consent-gated policy.",
        error_code=400,
        details={"reason_code": reason_code},
    )
    if receipt is not None:
        await response_handler.emit_json("OPENCARE_RECEIPT", redacted(receipt))


class OpenCareSentientDemoAgent(AbstractAgent):
    """Sentient agent backed by a fixed synthetic OpenCare demo context."""

    def __init__(self, name: str, context: DemoContext) -> None:
        super().__init__(name)
        self._context = context

    async def assist(
        self,
        session: Session,
        query: Query,
        response_handler: ResponseHandler,
    ) -> None:
        try:
            await self._orchestrate(session, query, response_handler)
        except Exception:
            await response_handler.emit_error(
                "OpenCare adapter failed closed; no answer was produced.",
                error_code=500,
                details={"reason_code": "adapter_failed_closed"},
            )
        finally:
            await response_handler.complete()

    async def _orchestrate(
        self,
        session: Session,
        query: Query,
        response_handler: ResponseHandler,
    ) -> None:
        runtime: G2Runtime = self._context.runtime
        policy = classify_question(query.prompt)
        if policy.decision != "allowed":
            await _refuse(
                response_handler,
                reason_code=policy.reason_code,
                message=policy.response_text,
            )
            return
        try:
            prepared = runtime.prepare(
                self._context.session_token,
                query.prompt,
                purpose_id=PURPOSE_ID,
                action_id=ACTION_ID,
            )
        except (BuildRefused, PermissionError) as exc:
            await _refuse(response_handler, reason_code=str(exc) or "authorization_unavailable")
            return
        await response_handler.emit_json(
            "OPENCARE_STATUS",
            {
                "stage": "authorized",
                "purpose": PURPOSE_ID,
                "requested_action": ACTION_ID,
            },
        )
        fields = list(self._context.projection.allowed_fields)
        try:
            runtime.grant_disclosure_consent(
                self._context.session_token, prepared.execution_id, fields=fields
            )
        except (BuildRefused, PermissionError) as exc:
            await _refuse(response_handler, reason_code=str(exc) or "authorization_unavailable")
            return
        await response_handler.emit_json(
            "OPENCARE_STATUS",
            {
                "stage": "prepared",
                "purpose": PURPOSE_ID,
                "requested_action": ACTION_ID,
            },
        )
        result = runtime.execute(
            self._context.session_token, prepared.execution_id, query.prompt
        )
        receipt = runtime.get_receipt(self._context.session_token, prepared.execution_id)
        if receipt is None:
            await _refuse(
                response_handler,
                reason_code="adapter_failed_closed",
                message="OpenCare could not verify an execution receipt; refusing to answer.",
            )
            return
        if not isinstance(receipt, ExecutionReceipt):
            raise ValueError("unexpected receipt format")
        if result.status != "answered":
            await _refuse(
                response_handler,
                reason_code=result.reason_code or "execution_refused",
                message="OpenCare refused the request under its consent-gated safety policy.",
                receipt=receipt,
            )
            return
        await response_handler.emit_json(
            "OPENCARE_STATUS",
            {
                "stage": "validated",
                "purpose": PURPOSE_ID,
                "requested_action": ACTION_ID,
            },
        )
        await response_handler.emit_json("SOURCES", _sources_payload(self._context.projection))
        answer = result.answer
        if not isinstance(answer, dict) or not isinstance(answer.get("answer"), str):
            raise ValueError("invalid answer shape")
        await response_handler.emit_text_block("FINAL_RESPONSE", answer["answer"])
        await response_handler.emit_json("OPENCARE_RECEIPT", redacted(receipt))
