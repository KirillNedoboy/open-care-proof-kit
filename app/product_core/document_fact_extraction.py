from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from app.agent.providers.contract import AgentProvider, ProviderExecutionRequest
from app.product_core.models import (
    CandidateFact,
    ConditionCandidateDetail,
    DocumentFactExtractionItem,
    DocumentFactExtractionRun,
    DocumentFactItemStatus,
    DocumentFactRunStatus,
    FactType,
    LabCandidateDetail,
    MedicationCandidateDetail,
    normalize_medication_name,
)
from app.product_core.runtime import ProductCoreRuntime

CONTRACT_VERSION = "opencare-document-facts/1"
MAX_DOCUMENT_AI_TEXT_CHARS = 60_000
MAX_DOCUMENT_AI_FACTS = 32
MAX_DOCUMENT_AI_QUOTE_CHARS = 600


class MedicationSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1, le=200)
    evidence_quote: str = Field(min_length=1, max_length=MAX_DOCUMENT_AI_QUOTE_CHARS)
    display_name: str = Field(min_length=1, max_length=200)
    schedule_text: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)


class ConditionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1, le=200)
    evidence_quote: str = Field(min_length=1, max_length=MAX_DOCUMENT_AI_QUOTE_CHARS)
    display_name: str = Field(min_length=1, max_length=200)
    status_text: str | None = Field(default=None, max_length=500)
    onset_date: date | None = None
    note: str | None = Field(default=None, max_length=2000)


class LabSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1, le=200)
    evidence_quote: str = Field(min_length=1, max_length=MAX_DOCUMENT_AI_QUOTE_CHARS)
    test_name: str = Field(min_length=1, max_length=200)
    result_text: str = Field(default="", max_length=2000)
    unit_text: str | None = Field(default=None, max_length=500)
    reference_range_text: str | None = Field(default=None, max_length=500)
    observed_date: date | None = None
    source_flag_text: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)


class DocumentFactAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medications: list[MedicationSuggestion]
    conditions: list[ConditionSuggestion]
    labs: list[LabSuggestion]


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _now(runtime: ProductCoreRuntime) -> datetime:
    return runtime.clock().astimezone(UTC)


def _detail_payload(fact_type: str, suggestion: BaseModel) -> dict[str, object]:
    values = suggestion.model_dump(mode="json")
    values.pop("page_number", None)
    values.pop("evidence_quote", None)
    return values


def _semantic_grounding_ok(fact_type: str, quote: str) -> bool:
    """Require the quote to state the fact family, not merely imply it."""
    lowered = quote.casefold()
    if fact_type == "medication":
        return any(
            token in lowered
            for token in (
                "medication",
                "medications",
                "prescribed",
                "taking",
                "administered",
                "current",
            )
        )
    if fact_type == "condition":
        return any(
            token in lowered
            for token in ("diagnosis", "diagnosed", "condition", "history of", "problem list")
        )
    return True


def _quote_locator(source: Any, extraction: Any, page: Any, quote: str) -> dict[str, object]:
    if len(quote) > MAX_DOCUMENT_AI_QUOTE_CHARS:
        raise ValueError("quote_too_long")
    occurrences: list[int] = []
    offset = page.normalized_text.find(quote)
    while offset >= 0:
        occurrences.append(offset)
        offset = page.normalized_text.find(quote, offset + 1)
    if len(occurrences) != 1:
        raise ValueError("quote_not_unique")
    start = occurrences[0]
    end = start + len(quote)
    return {
        "kind": "document_text_span",
        "source_id": source.id,
        "content_hash": source.content_hash,
        "extraction_id": extraction.extraction_id,
        "page_number": page.page_number,
        "start_codepoint": start,
        "end_codepoint": end,
        "selected_text_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
    }


Suggestion = MedicationSuggestion | ConditionSuggestion | LabSuggestion


def _suggestions(answer: Any) -> list[tuple[FactType, Suggestion]]:
    if not isinstance(answer, dict):
        raise ValueError("invalid_structured_output")
    if set(answer) != {"medications", "conditions", "labs"}:
        raise ValueError("invalid_structured_output")
    parsed = DocumentFactAnswer.model_validate(answer)
    return [
        *[("medication", item) for item in parsed.medications],
        *[("condition", item) for item in parsed.conditions],
        *[("lab", item) for item in parsed.labs],
    ]


class DocumentFactExtractionService:
    def __init__(self, runtime: ProductCoreRuntime, provider: AgentProvider) -> None:
        self.runtime = runtime
        self.provider = provider

    def prepare(
        self, person_id: str, source_id: str, allowed_fact_types: list[str], *, actor_id: str
    ) -> dict[str, Any]:
        descriptor = self.provider.descriptor
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            source = uow.sources.get(source_id)
            if source is None or source.person_id != person_id or source.source_type != "document":
                raise ValueError("document_not_found")
            extraction = uow.document_extractions.get_complete_for_source(source_id)
            if extraction is None:
                raise ValueError("document_extraction_missing")
            request_fingerprint = _fingerprint(
                [
                    person_id,
                    source_id,
                    extraction.extraction_id,
                    extraction.text_hash,
                    CONTRACT_VERSION,
                    descriptor.descriptor_hash,
                    sorted(allowed_fact_types),
                ]
            )
            existing = uow.document_fact_extractions.get_run_by_fingerprint(
                person_id, source_id, extraction.extraction_id, request_fingerprint
            )
            if existing is not None and existing.status == "completed":
                return self.serialize_run(
                    existing,
                    uow.document_fact_extractions.list_items(existing.run_id),
                    page_count=extraction.page_count,
                    character_count=extraction.total_chars,
                )
            if extraction.total_chars > MAX_DOCUMENT_AI_TEXT_CHARS:
                now = _now(self.runtime)
                run = DocumentFactExtractionRun(
                    run_id=self.runtime.id_factory(),
                    person_id=person_id,
                    source_id=source_id,
                    extraction_id=extraction.extraction_id,
                    actor_id=actor_id,
                    request_fingerprint=request_fingerprint,
                    contract_version="opencare-document-facts/1",
                    status="unavailable",
                    allowed_fact_types=cast(list[FactType], sorted(allowed_fact_types)),
                    provider_id=descriptor.provider_id,
                    provider_kind=descriptor.provider_kind,
                    provider_descriptor_hash=descriptor.descriptor_hash,
                    model_id=descriptor.model_id,
                    external=descriptor.external,
                    reason_code="input_chars_limit_exceeded",
                    created_at=now,
                    updated_at=now,
                )
                uow.document_fact_extractions.insert_run(run)
                return self.serialize_run(
                    run,
                    [],
                    page_count=extraction.page_count,
                    character_count=extraction.total_chars,
                )
            now = _now(self.runtime)
            if descriptor.provider_id == "deterministic":
                status: DocumentFactRunStatus = "unavailable"
                reason_code = "automatic_analysis_unavailable"
            else:
                status = "consent_required" if descriptor.external else "prepared"
                reason_code = None
            run = DocumentFactExtractionRun(
                run_id=self.runtime.id_factory(),
                person_id=person_id,
                source_id=source_id,
                extraction_id=extraction.extraction_id,
                actor_id=actor_id,
                request_fingerprint=request_fingerprint,
                contract_version="opencare-document-facts/1",
                status=status,
                allowed_fact_types=cast(list[FactType], sorted(allowed_fact_types)),
                provider_id=descriptor.provider_id,
                provider_kind=descriptor.provider_kind,
                provider_descriptor_hash=descriptor.descriptor_hash,
                model_id=descriptor.model_id,
                external=descriptor.external,
                reason_code=reason_code,
                created_at=now,
                updated_at=now,
            )
            uow.document_fact_extractions.insert_run(run)
            return self.serialize_run(
                run, [], page_count=extraction.page_count, character_count=extraction.total_chars
            )

    def consent(
        self,
        run_id: str,
        decision: str,
        *,
        person_id: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        if decision == "decline":
            return self.decline(run_id)
        if decision != "approve":
            raise ValueError("invalid_consent_decision")
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            if (person_id is not None and run.person_id != person_id) or (
                source_id is not None and run.source_id != source_id
            ):
                raise ValueError("run_not_found")
            if run.external and run.status == "consent_required":
                run.status = "consented"
                run.updated_at = _now(self.runtime)
                uow.document_fact_extractions.update_run(run)
            return self.serialize_run(run, uow.document_fact_extractions.list_items(run_id))

    def execute(
        self,
        run_id: str,
        *,
        person_id: str | None = None,
        source_id: str | None = None,
        consent: bool = False,
        authorized_fact_types: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.runtime.database.uow() as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            if (person_id is not None and run.person_id != person_id) or (
                source_id is not None and run.source_id != source_id
            ):
                raise ValueError("run_not_found")
            if run.status in {"completed", "partial", "declined", "unavailable"}:
                return self.serialize_run(run, uow.document_fact_extractions.list_items(run_id))
            if run.external and run.status != "consented" and not consent:
                raise ValueError("consent_required")
            effective_fact_types = [
                item
                for item in run.allowed_fact_types
                if authorized_fact_types is None or item in authorized_fact_types
            ]
            if not effective_fact_types:
                raise ValueError("no_writable_fact_types")
            source = uow.sources.get(run.source_id)
            extraction = uow.document_extractions.get(run.extraction_id)
            if source is None or extraction is None:
                raise ValueError("document_not_found")
            pages = uow.document_extractions.list_pages(run.extraction_id)
        if self.provider.descriptor.provider_id == "deterministic":
            return self._finish_unavailable(run_id)
        representation = tuple(
            {"page_number": p.page_number, "text": p.normalized_text} for p in pages
        )
        request = ProviderExecutionRequest(
            question="Extract only explicit medication, condition, and lab facts from these pages.",
            purpose_id="document_fact_extraction",
            action_id="document.extract_facts",
            requested_action=(
                "Extract source-stated document facts without diagnosis or treatment advice."
            ),
            evidence=representation,
            allowed_tools=(),
            allowed_fields=tuple(effective_fact_types),
            output_contract=DocumentFactAnswer.model_json_schema(),
            system_instructions=(
                "Copy only the supplied document. Do not infer, diagnose, interpret labs, "
                "or recommend treatment. Every fact requires one exact verbatim quote; "
                "omit uncertainty."
            ),
            disclosure_constraints=("disclose_only_selected_fields",),
            prohibited_operations=("canonical_record_mutation", "diagnosis", "treatment_planning"),
        )
        try:
            result = self.provider.execute(request)
            if result.failure is not None or result.answer is None:
                raise ValueError("provider_failed")
            suggestions = _suggestions(result.answer)
        except Exception:
            return self._finish_failed(run_id, "provider_failed")
        if len(suggestions) > MAX_DOCUMENT_AI_FACTS:
            return self._finish_failed(run_id, "fact_count_limit_exceeded")
        return self._materialize(
            run_id, suggestions, source, extraction, pages, authorized_fact_types
        )

    def decline(self, run_id: str) -> dict[str, Any]:
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            run.status = "declined"
            run.updated_at = _now(self.runtime)
            run.completed_at = run.updated_at
            uow.document_fact_extractions.update_run(run)
            return self.serialize_run(run, uow.document_fact_extractions.list_items(run_id))

    def _finish_failed(self, run_id: str, reason: str) -> dict[str, Any]:
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            run.status = "failed"
            run.reason_code = reason
            run.updated_at = _now(self.runtime)
            run.completed_at = run.updated_at
            uow.document_fact_extractions.update_run(run)
            return self.serialize_run(run, uow.document_fact_extractions.list_items(run_id))

    def _finish_unavailable(self, run_id: str) -> dict[str, Any]:
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            run.status = "unavailable"
            run.reason_code = "automatic_analysis_unavailable"
            run.updated_at = _now(self.runtime)
            run.completed_at = run.updated_at
            uow.document_fact_extractions.update_run(run)
            return self.serialize_run(run, uow.document_fact_extractions.list_items(run_id))

    def _materialize(
        self,
        run_id: str,
        suggestions: list[tuple[FactType, Suggestion]],
        source: Any,
        extraction: Any,
        pages: list[Any],
        authorized_fact_types: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
            run = uow.document_fact_extractions.get_run(run_id)
            if run is None:
                raise ValueError("run_not_found")
            valid = 0
            invalid = 0
            new = 0
            reused = 0
            items: list[DocumentFactExtractionItem] = []
            page_by_number = {p.page_number: p for p in pages}
            seen: set[str] = set()
            for ordinal, (fact_type, suggestion) in enumerate(suggestions):
                quote = str(suggestion.evidence_quote)
                page = page_by_number.get(int(suggestion.page_number))
                reason: str | None = None
                locator: dict[str, object] | None = None
                if fact_type not in run.allowed_fact_types or (
                    authorized_fact_types is not None and fact_type not in authorized_fact_types
                ):
                    reason = "fact_type_not_allowed"
                elif page is None:
                    reason = "page_not_found"
                elif not all(
                    str(value) in quote
                    for value in _detail_payload(fact_type, suggestion).values()
                    if value not in (None, "")
                ):
                    reason = "detail_not_explicit"
                elif not _semantic_grounding_ok(fact_type, quote):
                    reason = "fact_not_explicitly_stated"
                else:
                    try:
                        locator = _quote_locator(source, extraction, page, quote)
                        # Reuse the closed D1 validator before persisting any candidate.
                        self.runtime.lifecycle._validate_document_locator(uow, source, locator)
                    except ValueError as exc:
                        reason = str(exc)
                if reason is not None or locator is None:
                    invalid += 1
                    items.append(
                        self._item(
                            run, ordinal, fact_type, suggestion, "invalid", reason, None, None
                        )
                    )
                    continue
                detail_values = _detail_payload(fact_type, suggestion)
                fingerprint = _fingerprint(
                    [
                        run.person_id,
                        run.source_id,
                        run.extraction_id,
                        fact_type,
                        locator,
                        detail_values,
                    ]
                )
                if fingerprint in seen:
                    invalid += 1
                    items.append(
                        self._item(
                            run,
                            ordinal,
                            fact_type,
                            suggestion,
                            "invalid",
                            "duplicate_fact",
                            None,
                            fingerprint,
                        )
                    )
                    continue
                seen.add(fingerprint)
                valid += 1
                candidate_id = uow.document_fact_extractions.get_candidate_id_by_fingerprint(
                    run.person_id, fingerprint
                )
                was_reused = candidate_id is not None
                if candidate_id is None:
                    detail = self._detail(fact_type, suggestion)
                    candidate = CandidateFact(
                        id=self.runtime.id_factory(),
                        person_id=run.person_id,
                        source_id=run.source_id,
                        fact_type=fact_type,
                        detail=detail,
                        created_at=_now(self.runtime),
                        provenance_locator=locator,
                    )
                    uow.candidates.insert(candidate)
                    uow.document_fact_extractions.insert_fingerprint(
                        candidate_fingerprint=fingerprint,
                        person_id=run.person_id,
                        source_id=run.source_id,
                        fact_type=fact_type,
                        candidate_id=candidate.id,
                        created_at=_now(self.runtime),
                    )
                    candidate_id = candidate.id
                    new += 1
                else:
                    reused += 1
                items.append(
                    self._item(
                        run,
                        ordinal,
                        fact_type,
                        suggestion,
                        "reused" if was_reused else "valid",
                        None,
                        candidate_id,
                        fingerprint,
                        locator,
                    )
                )
            for item in items:
                uow.document_fact_extractions.insert_item(item)
            run.total_facts = len(suggestions)
            run.valid_facts = valid
            run.invalid_facts = invalid
            run.new_candidates = new
            run.reused_candidates = reused
            run.status = "completed" if invalid == 0 else ("partial" if valid else "failed")
            run.reason_code = None if valid or not suggestions else "no_source_valid_facts"
            run.updated_at = _now(self.runtime)
            run.completed_at = run.updated_at
            uow.document_fact_extractions.update_run(run)
            return self.serialize_run(run, items)

    def _detail(self, fact_type: FactType, suggestion: Suggestion) -> Any:
        values = _detail_payload(fact_type, suggestion)
        if fact_type == "medication":
            return MedicationCandidateDetail(
                display_name=str(values["display_name"]),
                normalized_name=normalize_medication_name(str(values["display_name"])),
                schedule_text=cast(str | None, values.get("schedule_text")),
                note=cast(str | None, values.get("note")),
            )
        if fact_type == "condition":
            return ConditionCandidateDetail(
                display_name=str(values["display_name"]),
                normalized_name=normalize_medication_name(str(values["display_name"])),
                status_text=cast(str | None, values.get("status_text")),
                onset_date=cast(date | None, values.get("onset_date")),
                note=cast(str | None, values.get("note")),
            )
        return LabCandidateDetail(
            test_name=str(values["test_name"]),
            normalized_test_name=normalize_medication_name(str(values["test_name"])),
            result_text=str(values.get("result_text", "")),
            unit_text=cast(str | None, values.get("unit_text")),
            reference_range_text=cast(str | None, values.get("reference_range_text")),
            observed_date=cast(date | None, values.get("observed_date")),
            source_flag_text=cast(str | None, values.get("source_flag_text")),
            note=cast(str | None, values.get("note")),
        )

    def _item(
        self,
        run: DocumentFactExtractionRun,
        ordinal: int,
        fact_type: FactType,
        suggestion: Suggestion,
        status: DocumentFactItemStatus,
        reason: str | None,
        candidate_id: str | None,
        fingerprint: str | None,
        locator: dict[str, object] | None = None,
    ) -> DocumentFactExtractionItem:
        return DocumentFactExtractionItem(
            item_id=self.runtime.id_factory(),
            run_id=run.run_id,
            person_id=run.person_id,
            source_id=run.source_id,
            extraction_id=run.extraction_id,
            ordinal=ordinal,
            fact_type=fact_type,
            payload=_detail_payload(fact_type, suggestion),
            quote=str(suggestion.evidence_quote),
            page_number=int(suggestion.page_number),
            start_codepoint=(None if locator is None else int(str(locator["start_codepoint"]))),
            end_codepoint=None if locator is None else int(str(locator["end_codepoint"])),
            selected_text_sha256=None if locator is None else str(locator["selected_text_sha256"]),
            validation_status=status,
            invalid_reason=reason,
            candidate_id=candidate_id,
            candidate_fingerprint=fingerprint,
            created_at=_now(self.runtime),
        )

    @staticmethod
    def serialize_run(
        run: DocumentFactExtractionRun,
        items: list[DocumentFactExtractionItem],
        *,
        page_count: int | None = None,
        character_count: int | None = None,
    ) -> dict[str, Any]:
        return {
            **run.model_dump(mode="json"),
            "page_count": page_count,
            "character_count": character_count,
            "retention": "provider_policy" if run.external else "request_only",
            "requires_consent": run.external and run.status == "consent_required",
            "items": [item.model_dump(mode="json") for item in items],
        }
