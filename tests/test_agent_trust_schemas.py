"""Versioned JSON Schemas: deterministic generation, drift detection, validation.

The committed schemas under ``schemas/agent-trust/`` are generated from the G1
pydantic contract models (never hand-authored). These tests regenerate them and
compare byte-for-byte, then validate the committed fixtures against the schemas
with a small local validator (no JSON Schema framework dependency).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.agent_trust.schemas import generate_schemas

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "agent-trust"
FIXTURES_DIR = ROOT / "fixtures" / "agent-trust"

SCHEMA_FILENAMES = (
    "trust-envelope.schema.json",
    "execution-receipt.schema.json",
    "authorization-snapshot.schema.json",
)

JSON_SCHEMA_META = "https://json-schema.org/draft/2020-12/schema"


def test_generation_is_deterministic() -> None:
    first = generate_schemas()
    second = generate_schemas()
    assert set(first) == set(SCHEMA_FILENAMES)
    assert first == second


def test_committed_schemas_do_not_drift_from_current_models() -> None:
    generated = generate_schemas()
    for filename, content in generated.items():
        committed = (SCHEMA_DIR / filename).read_bytes()
        assert committed == content, (
            f"{filename} has drifted from the contract models; "
            "run `python -m app.agent_trust.cli export-schemas`"
        )


def test_schema_files_declare_the_json_schema_meta_schema() -> None:
    for filename in SCHEMA_FILENAMES:
        doc = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert doc["$schema"] == JSON_SCHEMA_META


def test_schemas_preserve_g1_contract_version_literals() -> None:
    envelope = json.loads(
        (SCHEMA_DIR / "trust-envelope.schema.json").read_text(encoding="utf-8")
    )
    receipt = json.loads(
        (SCHEMA_DIR / "execution-receipt.schema.json").read_text(encoding="utf-8")
    )
    assert envelope["properties"]["contract_version"]["const"] == (
        "opencare-trust-envelope/1"
    )
    assert receipt["properties"]["contract_version"]["const"] == (
        "opencare-execution-receipt/1"
    )


def test_envelope_fixture_validates_against_its_schema() -> None:
    schema = _schema("trust-envelope.schema.json")
    instance = _instance("allowed-envelope.json")
    _assert_valid(instance, schema)


def test_all_receipt_fixtures_validate_against_receipt_schema() -> None:
    schema = _schema("execution-receipt.schema.json")
    for filename in (
        "allowed-receipt.json",
        "refused-before-envelope-receipt.json",
        "unsupported-action-receipt.json",
    ):
        _assert_valid(_instance(filename), schema)


def test_tampered_fixture_fails_schema_validation() -> None:
    schema = _schema("trust-envelope.schema.json")
    tampered = dict(_instance("allowed-envelope.json"))
    tampered["contract_version"] = "opencare-trust-envelope/2"
    assert not _validate(tampered, schema, schema)

    stripped = {key: value for key, value in tampered.items() if key != "safety"}
    stripped["contract_version"] = "opencare-trust-envelope/1"
    assert not _validate(stripped, schema, schema)


def test_tampered_receipt_fails_schema_validation() -> None:
    schema = _schema("execution-receipt.schema.json")
    tampered = dict(_instance("allowed-receipt.json"))
    tampered["status"] = "completed-ish"
    assert not _validate(tampered, schema, schema)


def _schema(filename: str) -> dict[str, object]:
    return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))


def _instance(filename: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / filename).read_bytes())


def _assert_valid(instance: object, schema: dict[str, object]) -> None:
    assert _validate(instance, schema, schema), f"fixture does not conform to {schema.get('title')}"


# -- small local JSON Schema validator (subset of draft 2020-12 used by pydantic) --

def _validate(
    instance: object, schema: dict[str, object], root: dict[str, object]
) -> bool:
    if "$ref" in schema:
        ref = str(schema["$ref"])
        assert ref.startswith("#/$defs/"), ref
        return _validate(instance, root["$defs"][ref.removeprefix("#/$defs/")], root)  # type: ignore[index]
    if "const" in schema:
        return instance == schema["const"]
    if "enum" in schema:
        return instance in schema["enum"]
    if "anyOf" in schema:
        return any(_validate(instance, variant, root) for variant in schema["anyOf"])
    if "type" in schema:
        return _validate_type(instance, schema, root)
    return True


def _validate_type(
    instance: object, schema: dict[str, object], root: dict[str, object]
) -> bool:
    kind = schema["type"]
    if kind == "null":
        return instance is None
    if kind == "boolean":
        return isinstance(instance, bool)
    if kind == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if kind == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if kind == "string":
        if not isinstance(instance, str):
            return False
        if "pattern" in schema and re.fullmatch(str(schema["pattern"]), instance) is None:
            return False
        if "minLength" in schema and len(instance) < schema["minLength"]:
            return False
        return "maxLength" not in schema or len(instance) <= schema["maxLength"]
    if kind == "array":
        if not isinstance(instance, list):
            return False
        if "minItems" in schema and len(instance) < schema["minItems"]:
            return False
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            return False
        items = schema.get("items")
        return all(_validate(item, items, root) for item in instance)
    if kind == "object":
        if not isinstance(instance, dict):
            return False
        properties = schema.get("properties", {})
        assert isinstance(properties, dict)
        if (
            schema.get("additionalProperties") is False
            and not set(instance).issubset(properties)
        ):
            return False
        for required in schema.get("required", []):
            if required not in instance:
                return False
        return all(
            key in properties and _validate(value, properties[key], root)
            for key, value in instance.items()
        )
    return True
