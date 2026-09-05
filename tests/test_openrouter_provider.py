from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent.provider import HttpResponse
from app.agent.providers.contract import ProviderExecutionRequest, ProviderUnavailableError
from app.agent.providers.openrouter import (
    OPENROUTER_CHAT_COMPLETIONS_URL,
    OpenRouterProvider,
    OpenRouterProviderConfig,
    _NoRedirectHandler,
)
from app.config import Settings
from app.main import _build_agent_provider


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
    return {"answer": "Only recorded context is available."}


def provider(*, post: object = None) -> OpenRouterProvider:
    return OpenRouterProvider(
        OpenRouterProviderConfig(
            api_key="R6_OPENROUTER_SECRET_DO_NOT_RENDER",
            model="synthetic/provider-model",
        ),
        post=post,  # type: ignore[arg-type]
    )


def test_descriptor_and_request_contract_are_external_and_bounded() -> None:
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
            body=json.dumps(
                {
                    "model": "synthetic/provider-model",
                    "choices": [{"message": {"content": json.dumps(answer())}}],
                }
            ).encode(),
        )

    result = provider(post=post).execute(request())

    descriptor = provider(post=post).descriptor
    assert descriptor.provider_id == "opencare.openrouter"
    assert descriptor.provider_kind == "external_http"
    assert descriptor.provider_mode == "external_provider"
    assert descriptor.endpoint_class == "non_loopback"
    assert descriptor.external is True
    assert descriptor.model_id == "synthetic/provider-model"
    assert result.answer == answer()
    assert result.model_id == "synthetic/provider-model"
    assert result.tool_calls == ()
    assert captured["url"] == OPENROUTER_CHAT_COMPLETIONS_URL
    assert captured["timeout"] == 15.0
    assert captured["limit"] == 1_000_000

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "synthetic/provider-model"
    assert body["stream"] is False
    assert body["provider"] == {"require_parameters": True}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == request().output_contract
    assert len(body["messages"]) == 2
    assert "A recorded item" in json.dumps(body)
    assert "R6_OPENROUTER_SECRET_DO_NOT_RENDER" not in json.dumps(body)
    assert captured["headers"]["Authorization"] == "Bearer R6_OPENROUTER_SECRET_DO_NOT_RENDER"


def test_schema_valid_response_is_accepted() -> None:
    def post(*_: object) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body=json.dumps(
                {
                    "model": "synthetic/provider-model",
                    "choices": [{"message": {"content": json.dumps(answer())}}],
                }
            ).encode(),
        )

    assert provider(post=post).execute(request()).answer == answer()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"model": "synthetic/provider-model", "choices": []}, "invalid structured output"),
        (
            {"model": "synthetic/provider-model", "choices": [{"message": {"content": ""}}]},
            "invalid structured output",
        ),
        (
            {
                "model": "synthetic/provider-model",
                "choices": [{"message": {"content": "not-json"}}],
            },
            "invalid structured output",
        ),
    ],
)
def test_malformed_chat_completion_fails_closed(body: dict[str, object], message: str) -> None:
    def post(*_: object) -> HttpResponse:
        return HttpResponse(status_code=200, body=json.dumps(body).encode())

    with pytest.raises(ProviderUnavailableError, match=message):
        provider(post=post).execute(request())


def test_model_identity_mismatch_fails_closed() -> None:
    def post(*_: object) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body=json.dumps(
                {
                    "model": "other-model",
                    "choices": [{"message": {"content": json.dumps(answer())}}],
                }
            ).encode(),
        )

    with pytest.raises(ProviderUnavailableError, match="unexpected model"):
        provider(post=post).execute(request())


def test_schema_invalid_response_fails_closed() -> None:
    invalid_request = request()
    object.__setattr__(
        invalid_request,
        "output_contract",
        {"type": "object", "required": ["answer"]},
    )

    def post(*_: object) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body=json.dumps(
                {
                    "model": "synthetic/provider-model",
                    "choices": [{"message": {"content": "{}"}}],
                }
            ).encode(),
        )

    with pytest.raises(ProviderUnavailableError, match="does not conform"):
        provider(post=post).execute(invalid_request)


@pytest.mark.parametrize(
    "response",
    [
        HttpResponse(status_code=502, body=b"upstream"),
        HttpResponse(status_code=200, body=b"x" * 1_000_001),
        HttpResponse(status_code=200, body=b"not-json"),
    ],
)
def test_http_failures_are_sanitized_and_fail_closed(response: HttpResponse) -> None:
    def post(*_: object) -> HttpResponse:
        return response

    with pytest.raises(ProviderUnavailableError):
        provider(post=post).execute(request())


def test_timeout_and_connection_fail_closed() -> None:
    for error in (TimeoutError(), OSError("network failed")):
        def post(*_: object, error: BaseException = error) -> HttpResponse:
            raise error

        with pytest.raises(ProviderUnavailableError):
            provider(post=post).execute(request())


def test_redirect_handler_never_follows_redirects() -> None:
    assert (
        _NoRedirectHandler().redirect_request(
            None, None, 302, "Found", None, "https://other"
        )
        is None
    )  # type: ignore[arg-type]


def test_provider_config_rejects_openrouter_auto_and_invalid_limits() -> None:
    with pytest.raises(ValueError, match="configured model"):
        OpenRouterProviderConfig(api_key="secret", model="openrouter/auto")
    with pytest.raises(ValueError, match="limits"):
        OpenRouterProviderConfig(api_key="secret", model="synthetic/model", timeout_seconds=0)


def test_from_settings_requires_openrouter_external_configuration() -> None:
    base = Settings(
        env="development", demo_mode=True, data_dir=__import__("pathlib").Path("data"),
        reports_dir=__import__("pathlib").Path("reports"), allow_cloud_llm=False,
        secret_key=None, access_password=None,
    )
    with pytest.raises(ProviderUnavailableError):
        OpenRouterProvider.from_settings(base)


def test_factory_selects_openrouter_without_changing_other_modes() -> None:
    settings = Settings(
        env="development",
        demo_mode=True,
        data_dir=Path("data"),
        reports_dir=Path("reports"),
        allow_cloud_llm=False,
        secret_key=None,
        access_password=None,
        agent_mode="openrouter",
        agent_allow_external_llm=True,
        openrouter_api_key="secret",
        openrouter_model="synthetic/provider-model",
    )

    selected = _build_agent_provider(settings)

    assert isinstance(selected, OpenRouterProvider)
