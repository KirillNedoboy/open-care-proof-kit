from collections.abc import Callable

import pytest

from app.config import load_settings
from app.health_vault.runtime_loader import load_active_vault


def test_policy_allows_recorded_medication_and_dosage_questions() -> None:
    from app.agent.policy import classify_question

    allowed_questions = [
        "Which medications are recorded in this vault?",
        "What dosage is recorded in the source?",
        "Which source contains the recorded medication?",
        "What questions about my recorded medication should I ask my doctor?",
    ]

    assert {classify_question(question).decision for question in allowed_questions} == {"allowed"}


def test_policy_blocks_prescriptive_requests_without_blocking_recorded_context() -> None:
    from app.agent.policy import classify_question

    blocked_questions = [
        "Should I take this medication?",
        "Which medication should I choose?",
        "Increase my dosage?",
        "Should I stop taking it?",
        "What diagnosis do I have?",
        "What treatment should I start?",
        "What does my genetic variant mean?",
    ]

    assert {classify_question(question).decision for question in blocked_questions} == {"blocked"}


def test_policy_returns_fixed_urgent_decision() -> None:
    from app.agent.policy import classify_question

    decision = classify_question("I am having chest pain and cannot breathe")

    assert decision.decision == "urgent"
    assert "emergency" in decision.response_text.lower()


def test_context_contains_sources_without_paths_or_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agent.context import build_agent_context

    monkeypatch.setenv("OPENCARE_TEST_SECRET", "never-expose-this")
    context = build_agent_context(load_active_vault(load_settings({})))
    dumped = context.model_dump_json()

    assert "source-medication-list-2026-03" in dumped
    assert "never-expose-this" not in dumped
    assert "C:\\" not in dumped
    assert "notes" not in dumped


def test_validation_accepts_safe_boundary_language_and_rejects_unsafe_recommendation() -> None:
    from app.agent.context import build_agent_context
    from app.agent.models import AgentAnswer, Citation
    from app.agent.validation import validate_answer

    context = build_agent_context(load_active_vault(load_settings({})))
    citation = Citation(
        source_id="source-medication-list-2026-03",
        claim="The source records sertraline as a current medication.",
    )
    safe_answer = AgentAnswer(
        status="answered",
        answer="OpenCare cannot diagnose this. This is not a treatment recommendation.",
        citations=[citation],
        boundary_notices=["Ask a licensed clinician before making medication changes."],
    )
    unsafe_answer = safe_answer.model_copy(update={"answer": "You should increase the dosage."})

    assert validate_answer(safe_answer, context).valid is True
    assert validate_answer(unsafe_answer, context).reason_code == "unsafe_prescriptive_claim"


def test_validation_rejects_unknown_citation() -> None:
    from app.agent.context import build_agent_context
    from app.agent.models import AgentAnswer, Citation
    from app.agent.validation import validate_answer

    context = build_agent_context(load_active_vault(load_settings({})))
    answer = AgentAnswer(
        status="answered",
        answer="Recorded context is available.",
        citations=[Citation(source_id="unknown-source", claim="Unsupported claim")],
    )

    assert validate_answer(answer, context).reason_code == "unknown_citation"


def test_external_provider_is_disabled_by_default() -> None:
    from app.agent.provider import (
        OpenAIResponsesProvider,
        ProviderUnavailableError,
    )

    with pytest.raises(ProviderUnavailableError, match="disabled"):
        OpenAIResponsesProvider.from_settings(load_settings({}))


def test_external_provider_rejects_malformed_and_sensitive_urls() -> None:
    from app.agent.provider import ExternalProviderConfig

    for url in [
        "ftp://example.com/v1/responses",
        "https://user:pass@example.com/v1/responses",
        "https://example.com/v1/responses?token=secret",
        "https://example.com/v1/responses#fragment",
    ]:
        with pytest.raises(ValueError):
            ExternalProviderConfig(endpoint_url=url, api_key="key", model="model")


def test_external_provider_handles_malformed_http_timeout_and_oversized_responses() -> None:
    from app.agent.provider import (
        ExternalProviderConfig,
        HttpResponse,
        OpenAIResponsesProvider,
        ProviderUnavailableError,
    )

    config = ExternalProviderConfig(
        endpoint_url="https://example.test/v1/responses",
        api_key="key",
        model="model",
    )
    fixtures: list[Callable[..., HttpResponse]] = [
        lambda *_args, **_kwargs: HttpResponse(status_code=200, body=b"not-json"),
        lambda *_args, **_kwargs: HttpResponse(status_code=502, body=b"provider error"),
        lambda *_args, **_kwargs: HttpResponse(status_code=200, body=b"x" * 1_000_001),
    ]
    for post in fixtures:
        with pytest.raises(ProviderUnavailableError):
            OpenAIResponsesProvider(config, post).answer({}, "question")

    def timeout(*_args: object, **_kwargs: object) -> HttpResponse:
        raise TimeoutError

    with pytest.raises(ProviderUnavailableError, match="timeout"):
        OpenAIResponsesProvider(config, timeout).answer({}, "question")

    def connection_failure(*_args: object, **_kwargs: object) -> HttpResponse:
        raise ConnectionError

    with pytest.raises(ProviderUnavailableError, match="connection"):
        OpenAIResponsesProvider(config, connection_failure).answer({}, "question")


def test_external_provider_parses_valid_structured_response() -> None:
    from app.agent.provider import ExternalProviderConfig, HttpResponse, OpenAIResponsesProvider

    provider = OpenAIResponsesProvider(
        ExternalProviderConfig(
            endpoint_url="https://example.test/v1/responses",
            api_key="key",
            model="model",
        ),
        lambda *_args, **_kwargs: HttpResponse(
            status_code=200,
            body=(
                b'{"output_text":"{\\"answer\\":\\"Recorded context\\",'
                b'\\"citations\\":[],\\"unknowns\\":[],\\"doctor_questions\\":[],'
                b'\\"boundary_notices\\":[]}"}'
            ),
        ),
    )

    assert provider.answer({}, "question")["answer"] == "Recorded context"


def test_external_provider_parses_standard_responses_output_and_requests_schema() -> None:
    from app.agent.provider import ExternalProviderConfig, HttpResponse, OpenAIResponsesProvider

    sent: list[bytes] = []

    def post(_url: str, body: bytes, _headers: object, *_args: object) -> HttpResponse:
        sent.append(body)
        return HttpResponse(
            status_code=200,
            body=(
                b'{"output":[{"content":[{"type":"output_text",'
                b'"text":"{\\"answer\\":\\"Recorded context\\",\\"citations\\":[],'
                b'\\"unknowns\\":[],\\"doctor_questions\\":[],\\"boundary_notices\\":[]}"}]}]}'
            ),
        )

    provider = OpenAIResponsesProvider(
        ExternalProviderConfig(
            endpoint_url="https://example.test/v1/responses",
            api_key="key",
            model="model",
        ),
        post,
    )

    assert provider.answer({}, "question")["answer"] == "Recorded context"
    assert b'"json_schema"' in sent[0]


def test_demo_service_returns_source_backed_doctor_questions() -> None:
    from app.agent.service import GuardedChatService

    service = GuardedChatService.for_settings(load_settings({}))
    answer = service.answer("Prepare questions for my doctor")

    assert answer.status == "answered"
    assert answer.doctor_questions
    assert answer.citations
    assert answer.citations[0].source_id == "source-primary-care-note-2026-01"


def test_demo_service_supports_timeline_sources_and_missing_information_questions() -> None:
    from app.agent.service import GuardedChatService

    service = GuardedChatService.for_settings(load_settings({}))

    assert service.answer("What changed since the latest recorded visit?").status == "answered"
    assert service.answer("Which information is source-backed?").citations
    assert service.answer("What information is missing?").unknowns


def test_demo_service_handles_recorded_dosage_without_recommendation() -> None:
    from app.agent.service import GuardedChatService

    answer = GuardedChatService.for_settings(load_settings({})).answer(
        "What dosage is recorded in the source?"
    )

    assert answer.status == "answered"
    assert "no recorded source-backed dosage" in answer.answer.lower()
    assert not answer.citations


def test_blocked_question_never_calls_provider() -> None:
    from app.agent.models import AgentAnswer
    from app.agent.service import GuardedChatService

    class FailingProvider:
        def answer(self, context: object, question: str) -> AgentAnswer:
            raise AssertionError("provider must not be called")

    service = GuardedChatService(
        context=__import__(
            "app.agent.context", fromlist=["build_agent_context"]
        ).build_agent_context(load_active_vault(load_settings({}))),
        provider=FailingProvider(),
        provider_mode="openai_responses",
    )

    answer = service.answer("Should I stop taking it?")

    assert answer.status == "refused"
    assert "cannot" in answer.answer.lower()


def test_service_fails_closed_when_provider_returns_unsafe_answer() -> None:
    from app.agent.context import build_agent_context
    from app.agent.service import GuardedChatService

    class UnsafeProvider:
        def answer(self, context: object, question: str) -> dict[str, object]:
            return {
                "status": "answered",
                "answer": "You should start taking this medication.",
                "citations": [
                    {
                        "source_id": "source-medication-list-2026-03",
                        "claim": "Unsafe response fixture.",
                    }
                ],
                "unknowns": [],
                "doctor_questions": [],
                "boundary_notices": [],
            }

    service = GuardedChatService(
        context=build_agent_context(load_active_vault(load_settings({}))),
        provider=UnsafeProvider(),
        provider_mode="openai_responses",
    )

    assert service.answer("Which medication is recorded?").status == "validation_failed"


def test_service_adds_answered_status_to_external_provider_contract() -> None:
    from app.agent.context import build_agent_context
    from app.agent.service import GuardedChatService

    class ExternalContractProvider:
        def answer(self, context: object, question: str) -> dict[str, object]:
            return {
                "answer": "Recorded medication context is available.",
                "citations": [
                    {
                        "source_id": "source-medication-list-2026-03",
                        "claim": "The medication record is available in the supplied context.",
                    }
                ],
                "unknowns": [],
                "doctor_questions": [],
                "boundary_notices": [],
            }

    service = GuardedChatService(
        context=build_agent_context(load_active_vault(load_settings({}))),
        provider=ExternalContractProvider(),
        provider_mode="openai_responses",
    )

    assert service.answer("Which medication is recorded?").status == "answered"


def test_audit_record_excludes_conversation_and_provider_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.agent.audit import emit_audit
    from app.agent.policy import classify_question

    with caplog.at_level("INFO", logger="opencare.agent.audit"):
        emit_audit(
            provider_mode="demo",
            policy=classify_question("Which medication is recorded?"),
            validation_result="passed",
            citation_source_ids=["source-medication-list-2026-03"],
            question_length=29,
            reason_code=None,
            latency_ms=1,
        )

    logged = caplog.text
    assert "Which medication is recorded?" not in logged
    assert "answer text" not in logged
    assert "source-medication-list-2026-03" in logged
