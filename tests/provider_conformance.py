"""Provider conformance: same assertions over deterministic and Ollama (mocked).

The Ollama transport is always injected/mocked — no real network. Both
providers must present the same observable contract to G2: descriptor,
structured answer, model identity, tool-call translation, and zero exposure
of Product Core objects.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.agent.g2_runtime import EnvelopeProjection
from app.agent.providers.contract import (
    ANSWER_SCHEMA,
    SYSTEM_INSTRUCTIONS,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    answer_conforms_to_schema,
    build_provider_execution_request,
)
from app.agent.providers.deterministic import DeterministicProvider
from app.agent.providers.ollama import (
    OllamaProvider,
    OllamaProviderConfig,
    _post_json_no_redirect,
)
from app.agent_trust.builders import EnvelopeRequest, TrustedEnvelopeBuilder
from app.agent_trust.models import ProviderDescriptorContract
from app.agent_trust.testing import SyntheticAuthority

MODEL = "test-model"
VALID_ANSWER = {
    "answer": "Recorded context only; no advice.",
    "citations": [],
    "unknowns": [],
    "doctor_questions": [],
    "boundary_notices": [],
}


def ollama_body(*, content: str | None = None, model: str = MODEL, tool_calls: Any = None) -> bytes:
    message: dict[str, Any] = {
        "content": json.dumps(VALID_ANSWER) if content is None else content,
    }
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return json.dumps(
        {
            "model": model,
            "done": True,
            "done_reason": "stop",
            "total_duration": 1234,
            "eval_count": 7,
            "message": message,
        }
    ).encode("utf-8")


def stub_post(body: bytes, status: int = 200) -> Callable[..., Any]:
    def post(
        _url: str, _payload: bytes, _headers: dict[str, str], _timeout: float, _max: int
    ) -> Any:
        return _http_response(status, body)

    return post


def _http_response(status: int, body: bytes) -> Any:
    from app.agent.provider import HttpResponse

    return HttpResponse(status_code=status, body=body)


def make_ollama(
    *,
    endpoint: str = "http://127.0.0.1:11434",
    model: str = MODEL,
    post: Callable[..., Any] | None = None,
) -> OllamaProvider:
    return OllamaProvider(
        OllamaProviderConfig(endpoint_url=endpoint, model=model),
        post=post,
    )


def make_request(**changes: Any) -> ProviderExecutionRequest:
    values: dict[str, Any] = {
        "question": "What medications are recorded?",
        "purpose_id": "visit_preparation",
        "action_id": "summarize_records",
        "requested_action": "Summarize selected records for visit preparation.",
        "evidence": (
            {
                "evidence_id": "evidence-medication-alice",
                "selected_fields": ("medication.name", "medication.status"),
                "source_ids": ("source-alice",),
            },
        ),
        "allowed_tools": ("context.read", "source.read"),
        "allowed_fields": ("medication.name", "medication.status"),
        "output_contract": dict(ANSWER_SCHEMA),
        "system_instructions": SYSTEM_INSTRUCTIONS,
        "disclosure_constraints": ("disclose_only_selected_fields",),
        "prohibited_operations": ("canonical_record_mutation",),
    }
    values.update(changes)
    return ProviderExecutionRequest(**values)


@pytest.fixture(
    params=[
        "deterministic",
        "ollama_loopback",
        "ollama_external",
    ]
)
def provider(request: pytest.FixtureRequest) -> Any:
    if request.param == "deterministic":
        return DeterministicProvider()
    endpoint = (
        "http://127.0.0.1:11434"
        if request.param == "ollama_loopback"
        else "https://model-host.example"
    )
    return make_ollama(endpoint=endpoint, post=stub_post(ollama_body()))


def _descriptor_contract(provider: Any) -> ProviderDescriptorContract:
    d = provider.descriptor
    return ProviderDescriptorContract(
        provider_id=d.provider_id,
        model_id=d.model_id,
        provider_kind=d.provider_kind,
        endpoint_class=d.endpoint_class,
        external=d.external,
        descriptor_hash=d.descriptor_hash,
    )


def test_provider_descriptor_fields(provider: Any) -> None:
    descriptor = provider.descriptor
    assert descriptor.provider_id
    assert descriptor.provider_kind in {"deterministic", "self_hosted_http", "external_http"}
    assert descriptor.provider_mode in {"local_only", "external_provider"}
    assert descriptor.endpoint_class in {"loopback", "non_loopback", "none"}
    assert descriptor.external == (descriptor.endpoint_class == "non_loopback")
    assert len(descriptor.descriptor_hash) == 64
    assert descriptor.descriptor_hash == descriptor.descriptor_hash
    contract = _descriptor_contract(provider)
    assert contract.descriptor_hash == descriptor.descriptor_hash
    assert contract.model_id == descriptor.model_id


def test_external_flag_matches_endpoint_class(provider: Any) -> None:
    descriptor = provider.descriptor
    if descriptor.endpoint_class == "non_loopback":
        assert descriptor.external is True
        assert descriptor.provider_mode == "external_provider"
    else:
        assert descriptor.external is False


def test_descriptor_hash_changes_when_model_changes() -> None:
    first = make_ollama(model="model-a")
    second = make_ollama(model="model-b")
    assert first.descriptor.descriptor_hash != second.descriptor.descriptor_hash
    assert first.descriptor.provider_id == second.descriptor.provider_id


def test_structured_answer_result_for_valid_request(provider: Any) -> None:
    result = provider.execute(make_request())
    assert result.failure is None
    assert result.answer is not None
    assert answer_conforms_to_schema(result.answer, ANSWER_SCHEMA)
    assert set(result.answer) == {
        "answer",
        "citations",
        "unknowns",
        "doctor_questions",
        "boundary_notices",
    }
    assert result.provider_id == provider.descriptor.provider_id
    assert result.tool_calls == ()


def test_model_identity(provider: Any) -> None:
    result = provider.execute(make_request())
    assert result.model_id == provider.descriptor.model_id
    if provider.descriptor.provider_kind == "deterministic":
        assert result.model_id is None
    else:
        assert result.model_id == MODEL


def test_deterministic_answer_derives_only_from_evidence_and_fields() -> None:
    result = DeterministicProvider().execute(make_request())
    assert result.answer is not None
    assert result.answer["answer"] == (
        "Recorded context only: 1 evidence item(s) authorized; "
        "disclosed fields: medication.name, medication.status. This is recorded "
        "context only; no diagnosis, treatment, dosage, or medication advice is provided."
    )
    empty = DeterministicProvider().execute(
        make_request(evidence=(), allowed_fields=())
    )
    assert empty.answer is not None
    assert "0 evidence item(s)" in empty.answer["answer"]
    assert "disclosed fields: none" in empty.answer["answer"]


def test_provider_unavailable_fails_closed() -> None:
    def connection_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise ConnectionError("refused")

    ollama = make_ollama(post=connection_failure)
    with pytest.raises(Exception, match="provider|Provider"):
        ollama.execute(make_request())
    from app.agent.providers.contract import ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        ollama.execute(make_request())


def test_timeout_fails_closed() -> None:
    def timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise TimeoutError

    ollama = make_ollama(post=timeout)
    with pytest.raises(Exception, match="timeout"):
        ollama.execute(make_request())


def test_malformed_response_fails_closed() -> None:
    from app.agent.providers.contract import ProviderUnavailableError

    for body in (b"not-json", b"", b'{"model": "test-model"}', b"[1, 2, 3]"):
        ollama = make_ollama(post=stub_post(body))
        with pytest.raises(ProviderUnavailableError):
            ollama.execute(make_request())
    ollama = make_ollama(post=stub_post(b"x" * 1_000_001))
    with pytest.raises(ProviderUnavailableError):
        ollama.execute(make_request())
    ollama = make_ollama(post=stub_post(b"provider error", status=502))
    with pytest.raises(ProviderUnavailableError):
        ollama.execute(make_request())


def test_empty_answer_content_fails_closed() -> None:
    from app.agent.providers.contract import ProviderUnavailableError

    ollama = make_ollama(post=stub_post(ollama_body(content="")))
    with pytest.raises(ProviderUnavailableError):
        ollama.execute(make_request())


def test_invalid_structured_answer_fails_closed() -> None:
    from app.agent.providers.contract import ProviderUnavailableError

    invalid_shapes = [
        "not json at all",
        json.dumps({"answer": 42}),
        json.dumps({"answer": "ok"}),  # missing required keys
        json.dumps(
            {
                "answer": "ok",
                "citations": [],
                "unknowns": [],
                "doctor_questions": [],
                "boundary_notices": [],
                "extra": 1,
            }
        ),
        json.dumps([1, 2]),
    ]
    for content in invalid_shapes:
        ollama = make_ollama(post=stub_post(ollama_body(content=content)))
        with pytest.raises(ProviderUnavailableError):
            ollama.execute(make_request())


def test_unexpected_model_identity_fails_closed() -> None:
    ollama = make_ollama(post=stub_post(ollama_body(model="other-model")))
    with pytest.raises(Exception, match="model"):
        ollama.execute(make_request())


def test_tool_request_translation() -> None:
    tool_calls = [
        {
            "function": {
                "name": "source.read",
                "arguments": json.dumps({"evidence_id": "evidence-medication-alice"}),
            }
        },
        {
            "function": {
                "name": "context.read",
                "arguments": {"extra": "ignored"},
            }
        },
    ]
    ollama = make_ollama(post=stub_post(ollama_body(tool_calls=tool_calls)))
    result = ollama.execute(make_request())
    assert [call.tool for call in result.tool_calls] == ["source.read", "context.read"]
    assert all(call.operation == "read" for call in result.tool_calls)
    assert result.answer is not None
    assert result.answer["answer"].startswith("Recorded context")


def test_unknown_and_malformed_tool_entries_are_stripped() -> None:
    tool_calls = [
        {"function": {"name": "source.read", "arguments": "{}"}},
        {"function": {"name": 42}},
        {"not": "a function"},
        {"function": {"name": "brief.draft", "arguments": "not-json"}},
        None,
        "garbage",
    ]
    ollama = make_ollama(post=stub_post(ollama_body(tool_calls=tool_calls)))
    result = ollama.execute(make_request())
    assert [call.tool for call in result.tool_calls] == ["source.read", "brief.draft"]
    # Malformed arguments decode to an empty dict; the mediator enforces the allow-list.
    assert all(isinstance(call.arguments, dict) for call in result.tool_calls)


def test_runtime_metadata_is_bounded_observed_facts() -> None:
    ollama = make_ollama(post=stub_post(ollama_body()))
    result = ollama.execute(make_request())
    assert result.runtime_metadata.get("done_reason") == "stop"
    assert result.runtime_metadata.get("total_duration") == 1234
    assert result.runtime_metadata.get("eval_count") == 7
    assert "content" not in result.runtime_metadata
    assert "prompt" not in result.runtime_metadata
    assert "answer" not in result.runtime_metadata


def test_default_post_is_no_redirect_transport() -> None:
    assert make_ollama()._post is _post_json_no_redirect


def test_request_contains_only_projected_primitive_fields() -> None:
    """No Product Core object graph is ever exposed to a provider."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    authority = SyntheticAuthority.allowed(now=now)
    envelope = TrustedEnvelopeBuilder(authority, clock=lambda: now).build(
        EnvelopeRequest(
            actor_id="actor-alice",
            credential_id="credential-alice",
            person_id="person-alice",
            purpose_id="visit_preparation",
            action_id="summarize_records",
            requested_action="Summarize selected records.",
            requested_tools=["context.read", "source.read"],
            evidence_ids=["evidence-medication-alice"],
            disclosure_mode="local_only",
            provider_id=None,
            consent_basis_id="consent-alice",
            ttl_seconds=300,
        )
    )
    projection = EnvelopeProjection.from_envelope(envelope)
    request = build_provider_execution_request(projection, "What is recorded?")
    assert set(vars(request)) == {
        "question",
        "purpose_id",
        "action_id",
        "requested_action",
        "evidence",
        "allowed_tools",
        "allowed_fields",
        "output_contract",
        "system_instructions",
        "disclosure_constraints",
        "prohibited_operations",
    }
    assert all(isinstance(value, (str, tuple, dict)) for value in vars(request).values())
    assert all(
        set(item) == {"evidence_id", "selected_fields", "source_ids"}
        for item in request.evidence
    )
    assert all(
        isinstance(item["evidence_id"], str)
        and isinstance(item["selected_fields"], tuple)
        and all(isinstance(field, str) for field in item["selected_fields"])
        and isinstance(item["source_ids"], tuple)
        and all(isinstance(source_id, str) for source_id in item["source_ids"])
        for item in request.evidence
    )
    assert request.allowed_fields == ("medication.name", "medication.status")
    # The projection's Person id is NOT part of the provider request.
    assert "person_id" not in vars(request)
    # No envelope/authorization/evidence object graph leaks.
    assert not any(
        key in vars(request)
        for key in ("envelope_id", "person_id", "authorization", "safety", "evidence_items")
    )


def test_execution_result_failure_field_supported() -> None:
    from app.agent.providers.contract import ProviderFailure

    class FailingProvider(DeterministicProvider):
        def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
            del request
            return ProviderExecutionResult(
                answer=None,
                provider_id=self.descriptor.provider_id,
                model_id=None,
                tool_calls=(),
                failure=ProviderFailure(reason_code="provider_failed", message="boom"),
                runtime_metadata={},
            )

    result = FailingProvider().execute(make_request())
    assert result.failure is not None
    assert result.failure.reason_code == "provider_failed"
    assert result.answer is None
