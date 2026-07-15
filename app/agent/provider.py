import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import Settings

MAX_RESPONSE_BYTES = 1_000_000
PROVIDER_TIMEOUT_SECONDS = 15.0
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "citations", "unknowns", "doctor_questions", "boundary_notices"],
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_id", "claim"],
                "properties": {
                    "source_id": {"type": "string"},
                    "claim": {"type": "string"},
                },
            },
        },
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "doctor_questions": {"type": "array", "items": {"type": "string"}},
        "boundary_notices": {"type": "array", "items": {"type": "string"}},
    },
}


class ProviderUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes


@dataclass(frozen=True)
class ExternalProviderConfig:
    endpoint_url: str
    api_key: str
    model: str
    timeout_seconds: float = PROVIDER_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        if not _valid_endpoint(self.endpoint_url):
            raise ValueError("Invalid Responses endpoint URL.")
        if not self.api_key or not self.model:
            raise ValueError("External provider configuration is incomplete.")


HttpPost = Callable[[str, bytes, dict[str, str], float, int], HttpResponse]


class OpenAIResponsesProvider:
    def __init__(self, config: ExternalProviderConfig, post: HttpPost | None = None) -> None:
        self._config = config
        self._post = post or _post_json

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIResponsesProvider":
        if settings.agent_mode != "openai_responses" or not settings.agent_allow_external_llm:
            raise ProviderUnavailableError("External provider is disabled.")
        if not all((settings.llm_responses_url, settings.llm_api_key, settings.llm_model)):
            raise ProviderUnavailableError("External provider configuration is incomplete.")
        assert settings.llm_responses_url is not None
        assert settings.llm_api_key is not None
        assert settings.llm_model is not None
        return cls(
            ExternalProviderConfig(
                endpoint_url=settings.llm_responses_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        )

    def answer(self, context: object, question: str) -> dict[str, Any]:
        if not isinstance(context, dict):
            raise ProviderUnavailableError("External provider context is invalid.")
        payload = {
            "model": self._config.model,
            "input": [
                {"role": "system", "content": "Return only the required OpenCare JSON object."},
                {"role": "user", "content": json.dumps({"context": context, "question": question})},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "opencare_guarded_answer",
                    "strict": True,
                    "schema": ANSWER_SCHEMA,
                }
            },
        }
        try:
            response = self._post(
                self._config.endpoint_url,
                json.dumps(payload).encode("utf-8"),
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._config.api_key}",
                },
                self._config.timeout_seconds,
                self._config.max_response_bytes,
            )
        except TimeoutError as exc:
            raise ProviderUnavailableError("External provider timeout.") from exc
        except (OSError, URLError) as exc:
            raise ProviderUnavailableError("External provider connection failed.") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderUnavailableError("External provider request failed.")
        if len(response.body) > self._config.max_response_bytes:
            raise ProviderUnavailableError("External provider response was too large.")
        try:
            body = json.loads(response.body.decode("utf-8"))
            output_text = _extract_output_text(body)
            parsed_output = json.loads(output_text)
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise ProviderUnavailableError(
                "External provider returned invalid structured output."
            ) from exc
        if not isinstance(parsed_output, dict):
            raise ProviderUnavailableError("External provider returned invalid structured output.")
        return parsed_output


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
            text = content_item.get("text") if isinstance(content_item, dict) else None
            if (
                isinstance(content_item, dict)
                and content_item.get("type") == "output_text"
                and isinstance(text, str)
            ):
                return text
    raise KeyError("output_text")


def _valid_endpoint(url: str) -> bool:
    if any(ord(character) < 32 for character in url):
        return False
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _post_json(
    endpoint_url: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
) -> HttpResponse:
    request = Request(endpoint_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            content = response.read(max_response_bytes + 1)
            return HttpResponse(status_code=response.status, body=content)
    except TimeoutError:
        raise
    except URLError:
        raise
