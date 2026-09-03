from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.providers.deterministic import DeterministicProvider
from app.agent.providers.ollama import OllamaProvider, OllamaProviderConfig
from app.agent.providers.openai_responses import (
    OpenAIResponsesProvider,
    OpenAIResponsesProviderConfig,
)
from app.main import _provider_status
from app.ui_localization import get_translations


def _ollama(endpoint: str) -> OllamaProvider:
    return OllamaProvider(
        OllamaProviderConfig(
            endpoint_url=endpoint,
            model="synthetic-r6-model",
            timeout_seconds=1.0,
            max_response_bytes=1024,
        )
    )


def _openai() -> OpenAIResponsesProvider:
    return OpenAIResponsesProvider(
        OpenAIResponsesProviderConfig(
            endpoint_url="https://provider.example/v1/responses",
            api_key="R6_TEST_SECRET_DO_NOT_RENDER",
            model="synthetic-r6-openai-model",
        )
    )


def test_provider_status_is_a_safe_configured_projection() -> None:
    status = _provider_status(DeterministicProvider())

    assert status.provider_id == "opencare.deterministic.local"
    assert status.provider_kind == "deterministic"
    assert status.provider_mode == "local_only"
    assert status.model_id is None
    assert status.external is False
    assert status.configured is True
    assert "R6_TEST_SECRET_DO_NOT_RENDER" not in repr(status)


def test_provider_status_uses_ollama_descriptor_for_loopback_and_remote() -> None:
    local = _provider_status(_ollama("http://127.0.0.1:43765"))
    remote = _provider_status(_ollama("https://ollama.example"))

    assert (local.external, local.provider_mode, local.model_id) == (
        False,
        "local_only",
        "synthetic-r6-model",
    )
    assert (remote.external, remote.provider_mode, remote.model_id) == (
        True,
        "external_provider",
        "synthetic-r6-model",
    )


def test_provider_status_uses_openai_descriptor_without_credentials() -> None:
    status = _provider_status(_openai())

    assert status.provider_id == "opencare.openai_responses"
    assert status.provider_kind == "external_http"
    assert status.provider_mode == "external_provider"
    assert status.model_id == "synthetic-r6-openai-model"
    assert status.external is True
    assert "R6_TEST_SECRET_DO_NOT_RENDER" not in repr(status)


def test_provider_status_serialization_has_no_endpoint_or_secret_fields() -> None:
    status = _provider_status(_openai())

    assert set(asdict(status)) == {
        "provider_id",
        "provider_kind",
        "provider_mode",
        "model_id",
        "external",
        "configured",
    }
    assert "endpoint" not in asdict(status)
    assert "api_key" not in asdict(status)
    assert "R6_TEST_SECRET_DO_NOT_RENDER" not in str(asdict(status))


def test_provider_status_is_immutable() -> None:
    status = _provider_status(DeterministicProvider())

    with pytest.raises(AttributeError):
        status.external = True  # type: ignore[misc]


def test_settings_renders_deterministic_provider_metadata(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.get("/family-access")

    assert response.status_code == 200
    assert 'id="ai-provider"' in response.text
    assert "AI provider" in response.text
    assert "Deterministic test provider" in response.text
    assert "Local deterministic" in response.text
    assert "Managed by the OpenCare installation operator" in response.text
    assert "api_key" not in response.text.lower()
    assert "OPENCARE_LLM_API_KEY" not in response.text


def test_settings_localizes_provider_status_in_russian(
    product_core_client: TestClient,
) -> None:
    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    response = product_core_client.get("/family-access")

    assert response.status_code == 200
    assert '<html lang="ru">' in response.text
    assert "Провайдер ИИ" in response.text
    assert "Детерминированный тестовый провайдер" in response.text
    assert "Локальная детерминированная обработка" in response.text


def test_localization_contains_matching_provider_keys() -> None:
    english = get_translations("en")
    russian = get_translations("ru")

    expected = {
        "provider.heading",
        "provider.name_deterministic",
        "provider.name_ollama",
        "provider.name_openai",
        "provider.execution_deterministic",
        "provider.execution_local",
        "provider.execution_external",
        "provider.operator_managed",
        "provider.external_boundary",
        "provider.local_ollama_boundary",
    }
    assert expected <= set(english)
    assert set(english) == set(russian)


def test_boundary_copy_is_localized_and_secret_free() -> None:
    for locale in ("en", "ru"):
        catalog = get_translations(locale)
        assert "provider.external_boundary" in catalog
        assert "provider.local_ollama_boundary" in catalog
        assert "R6_TEST_SECRET_DO_NOT_RENDER" not in str(catalog)


def test_settings_has_no_provider_mutation_controls_or_browser_storage() -> None:
    template = Path("app/templates/family_access_workspace.html").read_text(encoding="utf-8")
    script = Path("app/static/family_access_workspace.js").read_text(encoding="utf-8")

    assert 'id="ai-provider"' in template
    assert "OPENCARE_AGENT_MODE" not in template
    assert "OPENCARE_LLM_API_KEY" not in template
    assert "localStorage" not in script


def test_chat_header_uses_descriptor_externality_for_non_loopback_ollama() -> None:
    template = Path("app/templates/chat.html").read_text(encoding="utf-8")
    settings_template = Path("app/templates/family_access_workspace.html").read_text(
        encoding="utf-8"
    )

    assert "provider_status.external" in template
    assert "provider_status.provider_kind" in template
    assert "Self-hosted model configured by operator" not in template
    assert "provider_status.external" in settings_template


def test_provider_templates_never_contain_provider_credentials() -> None:
    for path in (
        Path("app/templates/family_access_workspace.html"),
        Path("app/templates/chat.html"),
        Path("app/templates/chat_demo.html"),
    ):
        markup = path.read_text(encoding="utf-8")
        assert "OPENCARE_LLM_API_KEY" not in markup
        assert "R6_TEST_SECRET_DO_NOT_RENDER" not in markup
