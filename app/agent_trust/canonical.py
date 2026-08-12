from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.agent_trust.models import ExecutionReceipt, TrustEnvelope


class DuplicateKeyError(ValueError):
    pass


def strict_json_loads(data: bytes) -> Any:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("BOM is not canonical")
    if b"\r" in data:
        raise ValueError("CR is not canonical")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("document must be UTF-8") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise DuplicateKeyError(key)
            result[key] = value
        return result

    return json.loads(
        text,
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def canonical_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
    normalized = _normalize(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def envelope_id(envelope: TrustEnvelope | dict[str, Any]) -> str:
    payload = _payload(envelope)
    payload.pop("envelope_id", None)
    return f"sha256:{sha256_hex(canonical_bytes(payload))}"


def receipt_id(receipt: ExecutionReceipt | dict[str, Any]) -> str:
    payload = _payload(receipt)
    payload.pop("receipt_id", None)
    payload.pop("receipt_sha256", None)
    return f"sha256:{sha256_hex(canonical_bytes(payload))}"


def receipt_sha256(receipt: ExecutionReceipt | dict[str, Any]) -> str:
    payload = _payload(receipt)
    payload.pop("receipt_sha256", None)
    return sha256_hex(canonical_bytes(payload))


def digest_matches(actual: str, expected: str) -> bool:
    return hmac.compare_digest(actual, expected)


def _payload(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    return dict(value)


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("datetime must use UTC")
        utc = value.astimezone(UTC)
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        raise ValueError("floats are not part of the G1 contract")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")
