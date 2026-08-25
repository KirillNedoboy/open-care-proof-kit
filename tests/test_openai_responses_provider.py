from __future__ import annotations

import json

import pytest

from app.agent.provider import HttpResponse
from app.agent.providers.contract import ProviderExecutionRequest, ProviderUnavailableError
from app.agent.providers.openai_responses import (
    OpenAIResponsesProvider,
    OpenAIResponsesProviderConfig,
)


def request() -> ProviderExecutionRequest:
    return ProviderExecutionRequest(
        question="What is recorded?",
        purpose_id="record_explanation",
        action_id="answer_question",
        requested_action="Explain selected recorded evidence.",
        evidence=(
            {
                "evidence_id": "record-1",
                "selected_fields": ("medication.text",),
                "source_ids": ("source-1",),
                "content": {"kind": "medication", "text": "A recorded item"},
            },
        ),
        allowed_tools=("context.read", "source.read"),
        allowed_fields=("medication.text",),
        output_contract={"type": "object"},
        system_instructions="Use only supplied evidence.",
        disclosure_constraints=("disclose_only_selected_fields",),
        prohibited_operations=("canonical_record_mutation",),
    )


def answer() -> dict[str, object]:
    return {
        "answer": "Only recorded context is available.",
        "citations": [{"source_id": "source-1", "claim": "A recorded item"}],
        "unknowns": [],
        "doctor_questions": [],
        "boundary_notices": [],
    }


def test_responses_provider_implements_g2_contract_and_minimized_payload() -> None:
    captured: dict[str, object] = {}

    def post(
        url: str, body: bytes, headers: dict[str, str], timeout: float, limit: int
    ) -> HttpResponse:
        captured.update(
            url=url,
            body=json.loads(body),
            headers=headers,
            timeout=timeout,
            limit=limit,
        )
        return HttpResponse(
            status_code=200,
            body=json.dumps({"model": "gpt-test", "output_text": json.dumps(answer())}).encode(),
        )

    provider = OpenAIResponsesProvider(
        OpenAIResponsesProviderConfig(
            endpoint_url="https://provider.example/v1/responses",
            api_key="secret-value",
            model="gpt-test",
        ),
        post=post,
    )

    result = provider.execute(request())

    assert provider.descriptor.provider_id == "opencare.openai_responses"
    assert provider.descriptor.external is True
    assert result.answer == answer()
    assert result.model_id == "gpt-test"
    assert captured["url"] == "https://provider.example/v1/responses"
    body = captured["body"]
    assert isinstance(body, dict)
    serialized = json.dumps(body)
    assert "A recorded item" in serialized
    assert "secret-value" not in serialized


def test_responses_provider_fails_closed_on_model_identity_mismatch() -> None:
    def post(*_: object) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body=json.dumps({"model": "other-model", "output_text": json.dumps(answer())}).encode(),
        )

    provider = OpenAIResponsesProvider(
        OpenAIResponsesProviderConfig(
            endpoint_url="https://provider.example/v1/responses",
            api_key="secret-value",
            model="gpt-test",
        ),
        post=post,
    )

    with pytest.raises(ProviderUnavailableError, match="unexpected model"):
        provider.execute(request())


def test_responses_provider_fails_closed_on_non_success_or_invalid_output() -> None:
    def post(*_: object) -> HttpResponse:
        return HttpResponse(status_code=502, body=b"upstream failure")

    provider = OpenAIResponsesProvider(
        OpenAIResponsesProviderConfig(
            endpoint_url="https://provider.example/v1/responses",
            api_key="secret-value",
            model="gpt-test",
        ),
        post=post,
    )

    with pytest.raises(ProviderUnavailableError, match="request failed"):
        provider.execute(request())
