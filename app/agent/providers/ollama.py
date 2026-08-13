"""Self-hosted Ollama provider (Sentient G3).

The ONE real self-hosted adapter. Plain stdlib ``urllib`` HTTP — no SDK, no
dependency. Fails closed on timeout, connection failure, non-2xx, oversized
body, malformed JSON, missing/empty content, non-conforming structured output,
and unexpected model identity. A loopback endpoint can never redirect to an
external origin (redirects are not followed). No credentials in logs; the
endpoint/body are never logged.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.agent.provider import MAX_RESPONSE_BYTES, PROVIDER_TIMEOUT_SECONDS, HttpResponse
from app.agent.providers.contract import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderUnavailableError,
    ToolCall,
    answer_conforms_to_schema,
)
from app.agent.providers.endpoints import classify_endpoint
from app.config import Settings

#: Bounded token generation cap sent to the model (server-owned, not user-owned).
MAX_PREDICT_TOKENS = 1024

#: Bounded observed facts copied into runtime metadata (never raw output).
_METADATA_KEYS = (
    "done",
    "done_reason",
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)

HttpPost = Callable[[str, bytes, dict[str, str], float, int], HttpResponse]


@dataclass(frozen=True)
class OllamaProviderConfig:
    endpoint_url: str
    model: str
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama model must be non-empty.")
        classify_endpoint(self.endpoint_url)


class _NoRedirectHandler(HTTPRedirectHandler):
    """Never follow redirects: a loopback endpoint cannot pivot to an external host."""

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
            content = response.read(max_response_bytes + 1)
            return HttpResponse(status_code=response.status, body=content)
    except HTTPError as exc:
        # Includes 3xx that the no-redirect handler declined to follow.
        content = exc.read(max_response_bytes + 1)
        return HttpResponse(status_code=exc.code, body=content)
    except TimeoutError:
        raise
    except URLError:
        raise


class OllamaProvider:
    """Operator-configured self-hosted model runtime behind the Envelope."""

    def __init__(
        self, config: OllamaProviderConfig, post: HttpPost | None = None
    ) -> None:
        self._config = config
        self._post = post or _post_json_no_redirect
        self._endpoint_class = classify_endpoint(config.endpoint_url)

    @classmethod
    def from_settings(cls, settings: Settings) -> OllamaProvider:
        if settings.agent_mode != "ollama":
            raise ProviderUnavailableError("Ollama provider is disabled.")
        if not settings.ollama_endpoint or not settings.ollama_model:
            raise ProviderUnavailableError("Ollama provider configuration is incomplete.")
        return cls(
            OllamaProviderConfig(
                endpoint_url=settings.ollama_endpoint,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_timeout_seconds,
                max_response_bytes=settings.ollama_max_response_bytes,
            )
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id="opencare.ollama",
            provider_kind="self_hosted_http",
            provider_mode=(
                "local_only"
                if self._endpoint_class == "loopback"
                else "external_provider"
            ),
            endpoint_class=self._endpoint_class,
            external=self._endpoint_class == "non_loopback",
            model_id=self._config.model,
        )

    def _chat_url(self) -> str:
        base = self._config.endpoint_url.rstrip("/")
        if base.endswith("/api/chat"):
            return base
        return f"{base}/api/chat"

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": request.system_instructions},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": request.question,
                            "evidence": [dict(item) for item in request.evidence],
                            "allowed_fields": list(request.allowed_fields),
                            "allowed_tools": list(request.allowed_tools),
                            "purpose_id": request.purpose_id,
                            "action_id": request.action_id,
                            "requested_action": request.requested_action,
                            "disclosure_constraints": list(
                                request.disclosure_constraints
                            ),
                            "prohibited_operations": list(
                                request.prohibited_operations
                            ),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "format": request.output_contract,
            "stream": False,
            "options": {"temperature": 0, "num_predict": MAX_PREDICT_TOKENS},
        }
        try:
            response = self._post(
                self._chat_url(),
                json.dumps(payload).encode("utf-8"),
                {"Content-Type": "application/json"},
                self._config.timeout_seconds,
                self._config.max_response_bytes,
            )
        except TimeoutError as exc:
            raise ProviderUnavailableError("Ollama provider timeout.") from exc
        except (OSError, URLError) as exc:
            raise ProviderUnavailableError(
                "Ollama provider connection failed."
            ) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderUnavailableError("Ollama provider request failed.")
        if len(response.body) > self._config.max_response_bytes:
            raise ProviderUnavailableError("Ollama provider response was too large.")
        try:
            body = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError(
                "Ollama provider returned invalid JSON."
            ) from exc
        if not isinstance(body, dict):
            raise ProviderUnavailableError("Ollama provider returned invalid JSON.")
        returned_model = body.get("model")
        if returned_model != self._config.model:
            raise ProviderUnavailableError(
                "Ollama provider returned an unexpected model."
            )
        message = body.get("message")
        if not isinstance(message, dict):
            raise ProviderUnavailableError("Ollama provider returned no message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderUnavailableError(
                "Ollama provider returned no answer content."
            )
        try:
            answer = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError(
                "Ollama provider returned invalid structured output."
            ) from exc
        if not isinstance(answer, dict):
            raise ProviderUnavailableError(
                "Ollama provider returned invalid structured output."
            )
        if not answer_conforms_to_schema(answer, request.output_contract):
            raise ProviderUnavailableError(
                "Ollama provider output does not conform to the answer schema."
            )
        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        metadata = _bounded_metadata(body)
        return ProviderExecutionResult(
            answer=answer,
            provider_id=self.descriptor.provider_id,
            model_id=returned_model,
            tool_calls=tuple(tool_calls),
            failure=None,
            runtime_metadata=metadata,
        )


def _parse_tool_calls(raw: object) -> list[ToolCall]:
    """Translate ``message.tool_calls`` into mediated ``ToolCall`` values.

    Entries that are not well-formed ``{function: {name, arguments}}`` shapes
    are stripped; tool names are still enforced by the G2 mediator allow-list.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ProviderUnavailableError("Ollama provider returned invalid tool calls.")
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                parsed = {}
        elif isinstance(arguments, dict):
            parsed = arguments
        else:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        calls.append(ToolCall(tool=name, operation="read", arguments=parsed))
    return calls


def _bounded_metadata(body: dict[str, Any]) -> dict[str, Any]:
    """Copy only bounded observed facts; never raw output, prompt, or secrets."""
    metadata: dict[str, Any] = {}
    for key in _METADATA_KEYS:
        value = body.get(key)
        if isinstance(value, (bool, int, str)) or (
            isinstance(value, float) and math.isfinite(value)
        ):
            metadata[key] = value
    return metadata
