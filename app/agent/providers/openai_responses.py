"""G2-compatible OpenAI Responses provider.

The adapter receives only ``ProviderExecutionRequest`` projections and never
the Trust Envelope or Product Core object graph. Redirects are deliberately
disabled so a configured endpoint cannot pivot a disclosure to another host.
"""

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
from app.agent.providers.endpoints import classify_endpoint
from app.config import _is_valid_responses_url

MAX_RESPONSE_BYTES = 1_000_000
PROVIDER_TIMEOUT_SECONDS = 15.0

HttpPost = Callable[[str, bytes, dict[str, str], float, int], HttpResponse]


@dataclass(frozen=True)
class OpenAIResponsesProviderConfig:
    endpoint_url: str
    api_key: str
    model: str
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not _is_valid_responses_url(self.endpoint_url):
            raise ValueError("Invalid Responses endpoint URL.")
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("Responses provider configuration is incomplete.")
        if self.timeout_seconds <= 0 or self.max_response_bytes <= 0:
            raise ValueError("Responses provider limits must be positive.")


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


class OpenAIResponsesProvider(AgentProvider):
    def __init__(
        self,
        config: OpenAIResponsesProviderConfig,
        post: HttpPost | None = None,
    ) -> None:
        self._config = config
        self._post = post or _post_json_no_redirect
        self._endpoint_class = classify_endpoint(config.endpoint_url)

    @classmethod
    def from_settings(cls, settings: Any) -> OpenAIResponsesProvider:
        if settings.agent_mode != "openai_responses" or not settings.agent_allow_external_llm:
            raise ProviderUnavailableError("External provider is disabled.")
        if not all((settings.llm_responses_url, settings.llm_api_key, settings.llm_model)):
            raise ProviderUnavailableError("External provider configuration is incomplete.")
        return cls(
            OpenAIResponsesProviderConfig(
                endpoint_url=settings.llm_responses_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id="opencare.openai_responses",
            provider_kind="external_http",
            provider_mode=(
                "local_only" if self._endpoint_class == "loopback" else "external_provider"
            ),
            endpoint_class=self._endpoint_class,
            external=self._endpoint_class == "non_loopback",
            model_id=self._config.model,
        )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        payload = {
            "model": self._config.model,
            "input": [
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
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "opencare_guarded_answer",
                    "strict": True,
                    "schema": request.output_contract,
                }
            },
        }
        try:
            response = self._post(
                self._config.endpoint_url,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._config.api_key}",
                },
                self._config.timeout_seconds,
                self._config.max_response_bytes,
            )
        except TimeoutError as exc:
            raise ProviderUnavailableError("Responses provider timeout.") from exc
        except (OSError, URLError) as exc:
            raise ProviderUnavailableError("Responses provider connection failed.") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderUnavailableError("Responses provider request failed.")
        if len(response.body) > self._config.max_response_bytes:
            raise ProviderUnavailableError("Responses provider response was too large.")
        try:
            body = json.loads(response.body.decode("utf-8"))
            returned_model = body.get("model")
            output_text = _extract_output_text(body)
            answer = json.loads(output_text)
        except (
            AttributeError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ProviderUnavailableError(
                "Responses provider returned invalid structured output."
            ) from exc
        if returned_model != self._config.model:
            raise ProviderUnavailableError("Responses provider returned an unexpected model.")
        if not isinstance(answer, dict) or not answer_conforms_to_schema(
            answer, request.output_contract
        ):
            raise ProviderUnavailableError(
                "Responses provider output does not conform to the answer schema."
            )
        return ProviderExecutionResult(
            answer=answer,
            provider_id=self.descriptor.provider_id,
            model_id=returned_model,
            tool_calls=(),
            failure=None,
            runtime_metadata={},
        )


def _extract_output_text(body: object) -> str:
    if not isinstance(body, dict):
        raise TypeError("Response body must be an object.")
    output_text = body.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = body.get("output")
    if not isinstance(output, list):
        raise KeyError("output_text")
    for output_item in output:
        if not isinstance(output_item, dict):
            continue
        content = output_item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if (
                isinstance(content_item, dict)
                and content_item.get("type") == "output_text"
                and isinstance(content_item.get("text"), str)
            ):
                return content_item["text"]
    raise KeyError("output_text")
