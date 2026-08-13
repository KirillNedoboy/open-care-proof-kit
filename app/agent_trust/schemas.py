"""Deterministic JSON Schema export for the portable trust contracts.

The checked-in schema files under ``schemas/agent-trust/`` are generated from
the G1 pydantic contract models via :meth:`pydantic.BaseModel.model_json_schema`
and serialized canonically (sorted keys, no timestamps, no absolute paths).
Never hand-edit the schema files: run ``export-schemas`` (CLI) or
``scripts/export_agent_trust_schemas.py`` to regenerate them.

The schemas are descriptive artifacts of the G1 models; the pydantic models
remain the canonical source of truth and keep their existing ``contract_version``
literals (``opencare-trust-envelope/1`` / ``opencare-execution-receipt/1``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent_trust.models import (
    AuthorizationSnapshot,
    ExecutionReceipt,
    TrustEnvelope,
)

#: JSON Schema meta-schema the exported files declare conformance to.
JSON_SCHEMA_META = "https://json-schema.org/draft/2020-12/schema"

#: Filename -> contract model. Order and names are part of the export contract.
SCHEMA_MODELS: tuple[tuple[str, type[BaseModel]], ...] = (
    ("trust-envelope.schema.json", TrustEnvelope),
    ("execution-receipt.schema.json", ExecutionReceipt),
    ("authorization-snapshot.schema.json", AuthorizationSnapshot),
)


def render_schema(schema: dict[str, Any]) -> bytes:
    """Serialize one generated schema canonically (sorted keys, stable bytes)."""
    rendered = {"$schema": JSON_SCHEMA_META, **schema}
    return (
        json.dumps(rendered, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
        + b"\n"
    )


def generate_schemas() -> dict[str, bytes]:
    """Return {filename: canonical bytes} for every committed schema file."""
    return {
        filename: render_schema(model.model_json_schema())
        for filename, model in SCHEMA_MODELS
    }


def default_schema_dir() -> Path:
    """Repo-owned schema directory (``<repo>/schemas/agent-trust``)."""
    return Path(__file__).resolve().parents[2] / "schemas" / "agent-trust"


def write_schemas(output_dir: Path) -> list[Path]:
    """Write the three schema files into ``output_dir``; returns written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, content in generate_schemas().items():
        target = output_dir / filename
        target.write_bytes(content)
        written.append(target)
    return written
