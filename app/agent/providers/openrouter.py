"""OpenRouter Chat Completions provider behind the OpenCare trust boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.agent.provider import HttpResponse
from app.agent.providers.contract import (
    AgentProvider,
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderUnavailableError,
    answer_conforms_to_schema,
)

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RESPONSE_BYTES = 1_000_000
PROVIDER_TIMEOUT_SECONDS = 15.0

HttpPost = Callable[[str, bytes, dict[str, str], float, int], HttpResponse]


@dataclass(frozen=True)
class OpenRouterProviderConfig:
    api_key: str
    model: str
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("OpenRouter provider configuration is incomplete.")
        if self.model.strip() == "openrouter/auto":
            raise ValueError("OpenRouter configured model must be explicit.")
        if self.timeout_seconds <= 0 or self.max_response_bytes <= 0:
            raise ValueError("OpenRouter provider limits must be positive.")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _post_json_no_redirect(
    endpoint_url: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
) -> HttpResponse:
    request = Request(endpoint_url, data=body, headers=headers, method="POST")
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310
            return HttpResponse(
                status_code=response.status,
                body=response.read(max_response_bytes + 1),
            )
    except HTTPError as exc:
        return HttpResponse(
            status_code=exc.code,
            body=exc.read(max_response_bytes + 1),
        )
    except TimeoutError:
        raise
    except URLError:
        raise


class OpenRouterProvider(AgentProvider):
    def __init__(
        self,
        config: OpenRouterProviderConfig,
        post: HttpPost | None = None,
    ) -> None:
        self._config = config
        self._post = post or _post_json_no_redirect

    @classmethod
    def from_settings(cls, settings: Any) -> OpenRouterProvider:
        if settings.agent_mode != "openrouter" or not settings.agent_allow_external_llm:
            raise ProviderUnavailableError("External provider is disabled.")
        if not all((settings.openrouter_api_key, settings.openrouter_model)):
            raise ProviderUnavailableError("External provider configuration is incomplete.")
        return cls(
            OpenRouterProviderConfig(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
            )
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id="opencare.openrouter",
            provider_kind="external_http",
            provider_mode="external_provider",
            endpoint_class="non_loopback",
            external=True,
            model_id=self._config.model,
        )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": request.system_instructions},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": request.question,
                            "purpose_id": request.purpose_id,
                            "action_id": request.action_id,
                            "requested_action": request.requested_action,
                            "evidence": [dict(item) for item in request.evidence],
                            "allowed_fields": list(request.allowed_fields),
                            "allowed_tools": list(request.allowed_tools),
                            "disclosure_constraints": list(request.disclosure_constraints),
                            "prohibited_operations": list(request.prohibited_operations),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "opencare_guarded_answer",
                    "strict": True,
                    "schema": request.output_contract,
                },
            },
            "provider": {"require_parameters": True},
        }
        try:
            response = self._post(
                OPENROUTER_CHAT_COMPLETIONS_URL,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._config.api_key}",
                },
                self._config.timeout_seconds,
                self._config.max_response_bytes,
            )
        except TimeoutError as exc:
            raise ProviderUnavailableError("OpenRouter provider timeout.") from exc
        except (OSError, URLError) as exc:
            raise ProviderUnavailableError("OpenRouter provider connection failed.") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderUnavailableError("OpenRouter provider request failed.")
        if len(response.body) > self._config.max_response_bytes:
            raise ProviderUnavailableError("OpenRouter provider response was too large.")
        try:
            body = json.loads(response.body.decode("utf-8"))
            returned_model = body.get("model")
            choices = body.get("choices")
            message = choices[0].get("message")
            content = message.get("content")
            answer = json.loads(content)
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ProviderUnavailableError(
                "OpenRouter provider returned invalid structured output."
            ) from exc
        if not isinstance(returned_model, str) or not returned_model:
            raise ProviderUnavailableError("OpenRouter provider returned an unexpected model.")
        if returned_model != self._config.model:
            raise ProviderUnavailableError("OpenRouter provider returned an unexpected model.")
        if not isinstance(answer, dict) or not answer_conforms_to_schema(
            answer, request.output_contract
        ):
            raise ProviderUnavailableError(
                "OpenRouter provider output does not conform to the answer schema."
            )
        return ProviderExecutionResult(
            answer=answer,
            provider_id=self.descriptor.provider_id,
            model_id=returned_model,
            tool_calls=(),
            failure=None,
            runtime_metadata={},
        )
