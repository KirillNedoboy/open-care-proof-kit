"""Deterministic provider: the conformance baseline (Sentient G3).

The answer derives only from the authorized ``ProviderExecutionRequest``
(evidence references + allowed fields); no transport, no model, no failure.
"""

from __future__ import annotations

from typing import Any

from app.agent.providers.contract import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)


class DeterministicProvider:
    """Local deterministic provider; identical observable answer across hosts."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id="opencare.deterministic.local",
            provider_kind="deterministic",
            provider_mode="local_only",
            endpoint_class="none",
            external=False,
            model_id=None,
        )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        evidence = request.evidence
        field_text = ", ".join(sorted(request.allowed_fields)) or "none"
        answer_text = (
            f"Recorded context only: {len(evidence)} evidence item(s) authorized; "
            f"disclosed fields: {field_text}. This is recorded context only; "
            "no diagnosis, treatment, dosage, or medication advice is provided."
        )
        answer: dict[str, Any] = {
            "answer": answer_text,
            "citations": [],
            "unknowns": [],
            "doctor_questions": [],
            "boundary_notices": [],
        }
        return ProviderExecutionResult(
            answer=answer,
            provider_id=self.descriptor.provider_id,
            model_id=None,
            tool_calls=(),
            failure=None,
            runtime_metadata={"provider_kind": self.descriptor.provider_kind},
        )
