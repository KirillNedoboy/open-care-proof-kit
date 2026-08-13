"""Machine-readable adversarial scenario corpus (schema + loader).

The corpus is a committed, deterministic list of scenarios. Each scenario names
the synthetic identities, the disclosure request, a scripted provider, the
expected security outcome, and the phase mutations the driver applies between
the G2 prepare → grant → execute steps.

``expected_evidence_ids`` / ``forbidden_evidence_ids`` are *synthetic evaluation
labels*: they encode which evidence the scenario's relevance model says should
(respectively must not) be disclosed, so the harness can compute precision /
recall / minimization. They are not part of the G1/G2/G3/G4 trust contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CORPUS_SCHEMA_VERSION: Literal["opencare-g5-corpus/1"] = "opencare-g5-corpus/1"

Outcome = Literal["answered", "refused", "refused_prepare", "refused_consent"]

CATEGORIES = (
    "identity_boundary",
    "evidence_isolation",
    "context_integrity",
    "authorization_revocation",
    "consent_revocation",
    "provider_identity",
    "provider_availability",
    "tool_boundary",
    "citation_integrity",
    "provenance",
    "safety",
    "receipt_integrity",
    "envelope_integrity",
    "replay_determinism",
    "minimization",
    "fixture_isolation",
)


class Phase(BaseModel):
    """One live-state mutation applied between runtime phases."""

    model_config = ConfigDict(extra="forbid")

    after: Literal["prepare", "grant"]
    op: str
    actor_id: str | None = None
    person_id: str | None = None
    evidence_id: str | None = None
    content: str | None = None
    provider_id: str | None = None
    model_id: str | None = None


class ProviderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: str
    provider_id: str = "opencare.deterministic.local"
    model_id: str | None = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["opencare-g5-corpus/1"] = CORPUS_SCHEMA_VERSION
    case_id: str = Field(min_length=1)
    category: str
    description: str = Field(min_length=1)
    actor_id: str
    credential_id: str
    person_id: str
    purpose_id: Literal["visit_preparation", "record_explanation", "clinician_briefing"]
    action_id: Literal["answer_question", "draft_visit_brief", "summarize_records"]
    requested_action: str
    requested_tools: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    question: str
    provider: ProviderSpec
    expected_outcome: Outcome
    expected_reason_codes: list[str] = Field(default_factory=list)
    expected_evidence_ids: list[str] = Field(default_factory=list)
    forbidden_evidence_ids: list[str] = Field(default_factory=list)
    provider_must_be_called: bool = False
    mutation_allowed: bool = False
    kind: Literal[
        "g2_flow", "tamper_receipt", "tamper_envelope", "replay", "fixture_misuse"
    ] = "g2_flow"
    phases: list[Phase] = Field(default_factory=list)


def default_corpus_path() -> Path:
    return Path(__file__).resolve().parent / "corpus.json"


def load_corpus(path: Path | None = None) -> list[Scenario]:
    source = path if path is not None else default_corpus_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"corpus {source} must be a JSON list of scenarios")
    return [Scenario.model_validate(item) for item in raw]


__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "CATEGORIES",
    "Outcome",
    "Phase",
    "ProviderSpec",
    "Scenario",
    "default_corpus_path",
    "load_corpus",
]
