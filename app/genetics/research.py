"""Selective Research Mode packets, structured output, and strict validation."""

from __future__ import annotations

# ruff: noqa: E501
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from hashlib import sha256
from typing import Any

from pydantic import Field

from app.genetics.models import (
    CandidateFinding,
    EpistemicStatus,
    EvidenceEntry,
    EvidenceLevel,
    FrozenModel,
    GenotypeObservation,
    ResearchMode,
    SelectedHealthRecord,
)


class ResearchPacket(FrozenModel):
    """Minimized selected context. Raw files and unrestricted records have no field."""

    person_id: str = Field(min_length=1)
    mode: ResearchMode
    selected_observations: dict[str, GenotypeObservation]
    selected_evidence: dict[str, EvidenceEntry]
    selected_findings: dict[str, CandidateFinding]
    selected_health_records: dict[str, SelectedHealthRecord]
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchClaim(FrozenModel):
    """One major claim with an explicit epistemic label and bounded citations."""

    claim: str = Field(min_length=1)
    epistemic_status: EpistemicStatus
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    person_record_ids: tuple[str, ...] = ()
    reasoning_summary: str = Field(min_length=1)
    limitations: tuple[str, ...]
    missing_information: tuple[str, ...]
    model_background: bool = False


class ResearchOutput(FrozenModel):
    """Required counterevidence-first sections returned by Research Mode."""

    what_may_be_happening: str = Field(min_length=1)
    evidence_supporting_it: tuple[str, ...] = Field(min_length=1)
    evidence_against_it: tuple[str, ...] = Field(min_length=1)
    alternative_explanations: tuple[str, ...] = Field(min_length=1)
    missing_information: tuple[str, ...] = Field(min_length=1)
    confidence_epistemic_status: EpistemicStatus
    questions_worth_investigating: tuple[str, ...] = Field(min_length=1)
    claims: tuple[ResearchClaim, ...] = Field(min_length=1)


class ResearchReceipt(FrozenModel):
    """Provider execution metadata containing identifiers, never genotype bytes."""

    person_id: str
    mode: ResearchMode
    selected_evidence_ids: tuple[str, ...]
    selected_health_record_ids: tuple[str, ...]
    provider_identity: str
    provider_class: str
    disclosure_consent_reference: str | None = None
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_validation_result: str
    created_at: datetime


_FORBIDDEN_INSTRUCTION = re.compile(
    r"\b(?:start|stop|change|switch|increase|decrease|take)\b.{0,80}\b"
    r"(?:taking|using|treatment|therapy|medication|dose|mg)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_CLINICAL_CLAIM = re.compile(
    r"\b(?:you have|these variants confirm|this proves|proves that your symptoms are caused by|"
    r"your symptoms are caused by|diagnosed with)\b",
    re.IGNORECASE,
)


def build_research_packet(
    *,
    person_id: str,
    mode: ResearchMode,
    observations: Iterable[GenotypeObservation],
    evidence_entries: Iterable[EvidenceEntry],
    findings: Iterable[CandidateFinding],
    selected_observation_ids: set[str],
    selected_evidence_ids: set[str],
    selected_finding_ids: set[str],
    selected_health_records: Mapping[str, Mapping[str, Any]],
) -> ResearchPacket:
    """Build a deterministic packet from exact selections and reject unknown IDs."""

    observation_index = {item.observation_id: item for item in observations}
    evidence_index = {item.evidence_id: item for item in evidence_entries}
    finding_index = {item.finding_id: item for item in findings}
    _require_known("observation", selected_observation_ids, observation_index)
    _require_known("evidence", selected_evidence_ids, evidence_index)
    _require_known("finding", selected_finding_ids, finding_index)
    _reject_raw_values(selected_health_records)

    selected_observations = {
        key: observation_index[key] for key in sorted(selected_observation_ids)
    }
    selected_evidence = {key: evidence_index[key] for key in sorted(selected_evidence_ids)}
    selected_findings = {key: finding_index[key] for key in sorted(selected_finding_ids)}
    health_records: dict[str, SelectedHealthRecord] = {}
    for record_id in sorted(selected_health_records):
        record = dict(selected_health_records[record_id])
        kind = record.pop("kind", None)
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"selected health record {record_id} requires a kind")
        health_records[record_id] = SelectedHealthRecord(
            record_id=record_id, kind=kind, data=record
        )

    context = {
        "person_id": person_id,
        "mode": mode.value,
        "selected_observations": {
            key: value.model_dump(mode="json") for key, value in selected_observations.items()
        },
        "selected_evidence": {
            key: value.model_dump(mode="json") for key, value in selected_evidence.items()
        },
        "selected_findings": {
            key: value.model_dump(mode="json") for key, value in selected_findings.items()
        },
        "selected_health_records": {
            key: value.model_dump(mode="json") for key, value in health_records.items()
        },
    }
    serialized = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return ResearchPacket(
        person_id=person_id,
        mode=mode,
        selected_observations=selected_observations,
        selected_evidence=selected_evidence,
        selected_findings=selected_findings,
        selected_health_records=health_records,
        context_hash=sha256(serialized.encode("utf-8")).hexdigest(),
    )


def validate_research_output(output: ResearchOutput, packet: ResearchPacket) -> ResearchOutput:
    """Reject invented citations, unlabelled background, and medication instructions."""

    allowed_evidence = set(packet.selected_evidence)
    allowed_records = set(packet.selected_health_records)
    top_level_citations = {item for item in output.evidence_supporting_it if item.startswith("ev-")}
    invented_top_level = top_level_citations - allowed_evidence
    if invented_top_level:
        raise ValueError(f"unauthorized evidence IDs: {sorted(invented_top_level)}")

    for claim in output.claims:
        cited = set(claim.supporting_evidence_ids) | set(claim.contradicting_evidence_ids)
        invented = cited - allowed_evidence
        if invented:
            raise ValueError(f"unauthorized evidence IDs: {sorted(invented)}")
        unauthorized_records = set(claim.person_record_ids) - allowed_records
        if unauthorized_records:
            raise ValueError(f"unauthorized Person record IDs: {sorted(unauthorized_records)}")
        if claim.epistemic_status is EpistemicStatus.SUPPORTED:
            supporting_entries = [
                packet.selected_evidence[evidence_id]
                for evidence_id in claim.supporting_evidence_ids
            ]
            strong_levels = {
                EvidenceLevel.CLINICAL,
                EvidenceLevel.HIGH,
                EvidenceLevel.MODERATE,
            }
            if not supporting_entries or any(
                entry.evidence_level not in strong_levels for entry in supporting_entries
            ):
                raise ValueError("supported claims require selected moderate-or-stronger evidence")
        if claim.model_background and claim.epistemic_status not in {
            EpistemicStatus.PLAUSIBLE,
            EpistemicStatus.SPECULATIVE,
        }:
            raise ValueError("model-background claims must be explicitly plausible or speculative")
        if packet.mode is ResearchMode.EVIDENCE and claim.model_background:
            raise ValueError("model-background claims are excluded from Evidence Mode")
        claim_text = f"{claim.claim} {claim.reasoning_summary}"
        lower_claim = claim_text.casefold()
        external_discussion = any(
            marker in lower_claim
            for marker in ("external claim", "literature says", "quoted claim")
        )
        if (
            _FORBIDDEN_INSTRUCTION.search(claim_text)
            or _UNSUPPORTED_CLINICAL_CLAIM.search(claim_text)
        ) and not external_discussion:
            raise ValueError("unsupported clinical or prescriptive claim")
    return output


def build_research_receipt(
    *,
    packet: ResearchPacket,
    provider_identity: str,
    provider_class: str,
    disclosure_consent_reference: str | None,
    output_validation_result: str,
    created_at: datetime,
) -> ResearchReceipt:
    """Create a minimized execution receipt from packet identifiers only."""

    return ResearchReceipt(
        person_id=packet.person_id,
        mode=packet.mode,
        selected_evidence_ids=tuple(sorted(packet.selected_evidence)),
        selected_health_record_ids=tuple(sorted(packet.selected_health_records)),
        provider_identity=provider_identity,
        provider_class=provider_class,
        disclosure_consent_reference=disclosure_consent_reference,
        context_hash=packet.context_hash,
        output_validation_result=output_validation_result,
        created_at=created_at,
    )


def _require_known(label: str, selected: set[str], index: Mapping[str, object]) -> None:
    unknown = selected - set(index)
    if unknown:
        raise ValueError(f"unknown selected {label} IDs: {sorted(unknown)}")


_RAW_CONTEXT_KEYWORDS = (
    "raw",
    "payload",
    "source_content",
    "genome_file",
    "genotype_file",
    "unindexed",
)
_GENOTYPE_ROW = re.compile(
    r"(?:^|\n)\s*(?:rs[0-9A-Za-z_-]+|\S+)\s+\S+\s+\d+\s+[ACGT-]{1,2}(?:\s|$)",
    re.IGNORECASE,
)


def _reject_raw_values(value: object, *, path: str = "selected_health_records") -> None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError(f"raw bytes are forbidden in research packets at {path}")
    if isinstance(value, str):
        if len(value) > 5_000 or _GENOTYPE_ROW.search(value):
            raise ValueError(f"raw genotype content is forbidden in research packets at {path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if any(token in normalized_key for token in _RAW_CONTEXT_KEYWORDS):
                raise ValueError(f"raw fields are forbidden in research packets at {path}.{key}")
            _reject_raw_values(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            _reject_raw_values(child, path=f"{path}[{index}]")
