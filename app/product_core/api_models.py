from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.product_core.models import ensure_utc_datetime

CandidateStatus = Literal["pending", "confirmed", "corrected", "rejected", "unsupported"]
FactType = Literal["medication", "condition", "lab"]

MAX_ID_LENGTH = 128
MAX_DISPLAY_NAME_LENGTH = 200
MAX_SCHEDULE_LENGTH = 500
MAX_NOTE_LENGTH = 2_000
MAX_SOURCE_CONTENT_BYTES = 262_144
MAX_VISIT_TITLE_LENGTH = 200
MAX_SELECTED_RECORDS = 100


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_identifier(value: str) -> str:
    if not value.strip():
        raise ValueError("identifier must not be blank")
    _reject_control_characters(value, "identifier")
    return value


def _reject_control_characters(value: str, field_name: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} must not contain control characters")
    return value


def _validate_display_name(value: str) -> str:
    _reject_control_characters(value, "display_name")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("display_name must not be blank")
    if len(cleaned) > MAX_DISPLAY_NAME_LENGTH:
        raise ValueError("display_name is too long")
    return cleaned


class ManualMedicationRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    schedule_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("schedule_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class ManualConditionDetail(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    status_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    onset_date: date | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("status_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class ManualSourceRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    medication: ManualMedicationRequest

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, value: str) -> str:
        return _validate_identifier(value)


class PlainTextSourceRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    content: str

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("content")
    @classmethod
    def validate_content_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_SOURCE_CONTENT_BYTES:
            raise ValueError("source content is too large")
        return value


class PersonCreateRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    date_of_birth: date | None = None
    confirm_owner_assignment: bool = Field(default=False, strict=True)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)


class PersonUpdateRequest(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    date_of_birth: date | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _validate_display_name(value)

    @model_validator(mode="after")
    def require_change(self) -> PersonUpdateRequest:
        if not self.model_fields_set & {"display_name", "date_of_birth"}:
            raise ValueError("an update field is required")
        return self


class MedicationCandidateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    source_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    schedule_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("person_id", "source_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("schedule_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class ConditionCandidateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    source_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    status_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    onset_date: date | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("person_id", "source_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("status_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class ManualConditionSourceRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    condition: ManualConditionDetail

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, value: str) -> str:
        return _validate_identifier(value)


class ManualLabDetail(APIModel):
    test_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    result_text: str = Field(default="", max_length=MAX_NOTE_LENGTH)
    unit_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    reference_range_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    observed_date: date | None = None
    source_flag_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)

    @field_validator("test_name")
    @classmethod
    def validate_test_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("unit_text", "reference_range_text", "source_flag_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class ManualLabSourceRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    lab: ManualLabDetail

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, value: str) -> str:
        return _validate_identifier(value)


class LabCandidateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    source_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    test_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    result_text: str = Field(default="", max_length=MAX_NOTE_LENGTH)
    unit_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    reference_range_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    observed_date: date | None = None
    source_flag_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("person_id", "source_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("test_name")
    @classmethod
    def validate_test_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("unit_text", "reference_range_text", "source_flag_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")


class LabCorrectRequest(APIModel):
    test_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    result_text: str = Field(default="", max_length=MAX_NOTE_LENGTH)
    unit_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    reference_range_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    observed_date: date | None = None
    source_flag_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    source_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("test_name")
    @classmethod
    def validate_test_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("unit_text", "reference_range_text", "source_flag_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str | None) -> str | None:
        return None if value is None else _validate_identifier(value)


class EmptyActionRequest(APIModel):
    pass


class CorrectCandidateRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    schedule_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    source_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("schedule_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str | None) -> str | None:
        return None if value is None else _validate_identifier(value)


class ConditionCorrectRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    status_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    onset_date: date | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    source_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)
    provenance_locator: dict[str, Any] | None = Field(default=None)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_display_name(value)

    @field_validator("status_text", "note")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "text")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str | None) -> str | None:
        return None if value is None else _validate_identifier(value)


class VisitBriefGenerateRequest(APIModel):
    visit_title: str = Field(min_length=1, max_length=MAX_VISIT_TITLE_LENGTH)
    visit_purpose: str | None = Field(default=None, max_length=MAX_VISIT_TITLE_LENGTH)
    scheduled_date: str | None = Field(default=None, max_length=MAX_VISIT_TITLE_LENGTH)
    generated_at: datetime
    selected_record_ids: (
        list[Annotated[str, Field(min_length=1, max_length=MAX_ID_LENGTH)]] | None
    ) = Field(
        default=None,
        max_length=MAX_SELECTED_RECORDS,
    )

    @field_validator("visit_title")
    @classmethod
    def validate_visit_title(cls, value: str) -> str:
        _reject_control_characters(value, "visit_title")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("visit_title must not be blank")
        return cleaned

    @field_validator("visit_purpose")
    @classmethod
    def validate_visit_purpose(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _reject_control_characters(value, "visit_purpose")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("visit_purpose must not be blank")
        return cleaned

    @field_validator("selected_record_ids")
    @classmethod
    def validate_record_ids(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        for value in values:
            _validate_identifier(value)
        if len(values) != len(set(values)):
            raise ValueError("selected_record_ids must be unique")
        return values

    @field_validator("scheduled_date")
    @classmethod
    def validate_scheduled_date(cls, value: str | None) -> str | None:
        return None if value is None else _reject_control_characters(value, "scheduled_date")

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitCreateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    title: str
    specialist: str | None = None
    scheduled_date: date | None = None

    @field_validator("person_id")
    @classmethod
    def validate_person_id(cls, value: str) -> str:
        return _validate_identifier(value)


class VisitUpdateRequest(APIModel):
    title: str | None = None
    specialist: str | None = None
    scheduled_date: date | None = None


class VisitQuestionCreateRequest(APIModel):
    question_text: str


class VisitQuestionUpdateRequest(APIModel):
    question_text: str | None = None
    position: int | None = None


class SourceResponse(APIModel):
    source_id: str
    person_id: str
    source_type: Literal["manual_entry", "plain_text", "genetics"]
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime


class PersonResponse(APIModel):
    person_id: str
    display_name: str
    date_of_birth: date | None
    created_at: datetime
    updated_at: datetime
    is_active: bool


class PeopleListResponse(APIModel):
    people: list[PersonResponse]


class WorkspaceCapabilities(APIModel):
    """Closed capability map for the current Actor on one Person.

    Each boolean maps 1:1 to the same-named scope string. candidate.read is a
    precondition for inbox listing present in every role base set and is NOT
    part of this shape.
    """

    person_update: bool
    source_write: bool
    document_read: bool
    document_write: bool
    candidate_review: bool
    medication_read: bool
    medication_write: bool
    condition_read: bool
    condition_write: bool
    lab_read: bool
    lab_write: bool
    timeline_read: bool
    visit_read: bool
    visit_write: bool
    brief_read: bool
    brief_write: bool
    brief_export: bool
    vault_export: bool
    chat_use: bool
    genetics_read: bool
    genetics_write: bool
    genetics_research: bool
    genetics_compare: bool
    genetics_export: bool


class WorkspaceCapabilitiesResponse(APIModel):
    person_id: str
    capabilities: WorkspaceCapabilities


class SourceRegistrationResponse(APIModel):
    created: bool
    source: SourceResponse


class SourceMetadataResponse(APIModel):
    """Safe, Person-isolated source provenance metadata.

    Never exposes the owning Person id, the server-side storage location,
    payload bytes, or provenance internals. integrity_verified is true only
    after the immutable payload hash has been verified server-side.
    """

    source_id: str
    source_type: Literal["manual_entry", "plain_text", "document", "genetics"]
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    integrity_verified: bool


class DocumentExtractionResponse(APIModel):
    extraction_id: str
    extractor: str
    extractor_version: str
    status: Literal["complete"]
    text_hash: str
    total_chars: int
    page_count: int
    extracted_at: datetime


class DocumentResponse(APIModel):
    source_id: str
    person_id: str
    source_type: Literal["document"]
    media_type: Literal["application/pdf", "text/plain"]
    content_hash: str
    size_bytes: int
    original_filename: str | None
    document_kind: Literal["pdf", "text"]
    created_at: datetime
    extraction: DocumentExtractionResponse


class DocumentRegistrationResponse(APIModel):
    created: bool
    document: DocumentResponse


class DocumentListResponse(APIModel):
    documents: list[DocumentResponse]


class DocumentPageResponse(APIModel):
    source_id: str
    extraction_id: str
    page_number: int
    normalized_text: str
    decoded_content_bytes: int
    extracted_chars: int
    page_hash: str


class CandidateResponse(APIModel):
    id: str
    person_id: str
    source_id: str
    fact_type: Literal["medication", "condition", "lab"]
    status: CandidateStatus
    display_name: str | None = None
    schedule_text: str | None = None
    note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    predecessor_candidate_id: str | None = None
    provenance_locator: dict[str, Any] | None = None


class CandidateListResponse(APIModel):
    candidates: list[CandidateResponse]


class ConditionCandidateResponse(APIModel):
    id: str
    person_id: str
    source_id: str
    fact_type: Literal["condition"] = "condition"
    status: CandidateStatus
    display_name: str
    status_text: str | None = None
    onset_date: date | None = None
    note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    predecessor_candidate_id: str | None = None
    provenance_locator: dict[str, Any] | None = None


class ConditionCandidateListResponse(APIModel):
    candidates: list[ConditionCandidateResponse]


class ConditionRecordResponse(APIModel):
    id: str
    person_id: str
    candidate_id: str
    source_id: str
    display_name: str
    status_text: str | None = None
    onset_date: date | None = None
    note: str | None = None
    confirmed_at: datetime
    is_active: bool
    superseded_by_record_id: str | None = None
    provenance_locator: dict[str, Any] | None = None
    predecessor_candidate_id: str | None = None


class ConditionRecordListResponse(APIModel):
    conditions: list[ConditionRecordResponse]


class LabCandidateResponse(APIModel):
    id: str
    person_id: str
    source_id: str
    fact_type: Literal["lab"] = "lab"
    status: CandidateStatus
    test_name: str
    result_text: str
    unit_text: str | None = None
    reference_range_text: str | None = None
    observed_date: date | None = None
    source_flag_text: str | None = None
    note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    predecessor_candidate_id: str | None = None
    provenance_locator: dict[str, Any] | None = None


class LabCandidateListResponse(APIModel):
    candidates: list[LabCandidateResponse]


class LabRecordResponse(APIModel):
    id: str
    person_id: str
    candidate_id: str
    source_id: str
    test_name: str
    result_text: str
    unit_text: str | None = None
    reference_range_text: str | None = None
    observed_date: date | None = None
    source_flag_text: str | None = None
    note: str | None = None
    confirmed_at: datetime
    is_active: bool
    superseded_by_record_id: str | None = None
    provenance_locator: dict[str, Any] | None = None
    predecessor_candidate_id: str | None = None


class LabRecordListResponse(APIModel):
    labs: list[LabRecordResponse]


class CanonicalMedicationResponse(APIModel):
    id: str
    person_id: str
    candidate_id: str
    source_id: str
    fact_type: Literal["medication", "condition", "lab"]
    display_name: str | None = None
    schedule_text: str | None = None
    note: str | None = None
    confirmed_at: datetime
    is_active: bool
    superseded_by_record_id: str | None = None
    provenance_locator: dict[str, Any] | None = None
    predecessor_candidate_id: str | None = None


class CanonicalMedicationListResponse(APIModel):
    medications: list[CanonicalMedicationResponse]


class TimelineEventResponse(APIModel):
    id: str
    person_id: str
    canonical_record_id: str
    source_id: str
    fact_type: Literal["medication", "condition", "lab"]
    event_type: str
    event_at: datetime
    title: str


class TimelineResponse(APIModel):
    events: list[TimelineEventResponse]


class VisitResponse(APIModel):
    visit_id: str
    person_id: str
    title: str
    specialist: str | None
    scheduled_date: date | None
    created_at: datetime
    updated_at: datetime


class VisitListResponse(APIModel):
    visits: list[VisitResponse]


class VisitQuestionResponse(APIModel):
    question_id: str
    visit_id: str
    question_text: str
    position: int
    created_at: datetime
    updated_at: datetime


class VisitQuestionListResponse(APIModel):
    questions: list[VisitQuestionResponse]


class VisitBriefRecordResponse(APIModel):
    id: str
    display_name: str
    schedule_text: str | None
    note: str | None
    source_id: str


class VisitBriefResponse(APIModel):
    person_id: str
    visit_title: str
    visit_purpose: str
    scheduled_date: str | None
    generated_at: datetime
    records: list[VisitBriefRecordResponse]
    source_references: list[str]
    markdown: str


class VisitBriefInitializeResponse(APIModel):
    visit_id: str
    current_revision_number: int | None
    created_at: datetime
    updated_at: datetime


class VisitBriefEvidenceRequest(APIModel):
    selected_record_ids: list[Annotated[str, Field(min_length=1, max_length=MAX_ID_LENGTH)]] = (
        Field(max_length=MAX_SELECTED_RECORDS)
    )

    @field_validator("selected_record_ids")
    @classmethod
    def validate_record_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            _validate_identifier(value)
        if len(values) != len(set(values)):
            raise ValueError("selected_record_ids must be unique")
        return values


class VisitBriefGenerateRevisionRequest(VisitBriefEvidenceRequest):
    expected_current_revision_number: int | None = Field(..., ge=1)


class VisitBriefUserEditRequest(APIModel):
    preparation_notes: str = Field(max_length=MAX_NOTE_LENGTH)
    expected_current_revision_number: int = Field(ge=1)

    @field_validator("preparation_notes")
    @classmethod
    def validate_notes(cls, value: str) -> str:
        return (
            _reject_control_characters(value, "preparation_notes") if "\n" not in value else value
        )


class VisitBriefRestoreRequest(APIModel):
    revision_number: int = Field(ge=1)
    expected_current_revision_number: int = Field(ge=1)


class VisitBriefStalenessResponse(APIModel):
    state: Literal["current", "stale", "unavailable"]
    reasons: list[str]


class VisitBriefRevisionResponse(APIModel):
    revision_number: int
    origin: Literal["deterministic_generation", "user_edit", "regeneration"]
    parent_revision_number: int | None
    content_schema_version: int
    render_version: int
    created_at: datetime
    content: dict[str, Any]
    markdown: str
    staleness: VisitBriefStalenessResponse


class VisitBriefRevisionListResponse(APIModel):
    revisions: list[VisitBriefRevisionResponse]


class VisitBriefResponseV2(APIModel):
    visit_id: str
    current_revision_number: int | None
    created_at: datetime
    updated_at: datetime
    current_revision: VisitBriefRevisionResponse | None


class VisitBriefEligibleEvidenceResponse(APIModel):
    evidence: list[dict[str, Any]]


class VisitBriefEvidenceValidationResponse(APIModel):
    valid: bool
    selection_fingerprint: str
    evidence: list[dict[str, Any]]


class GeneticsConsentRequest(APIModel):
    confirmation: bool
    scopes: list[
        Literal[
            "genetics.read",
            "genetics.write",
            "genetics.research",
            "genetics.compare",
            "genetics.export",
        ]
    ] = Field(min_length=1)


class GeneticsGrantRequest(GeneticsConsentRequest):
    actor_id: str = Field(min_length=1)


class GeneticsImportRequest(APIModel):
    filename: str = Field(min_length=1, max_length=255)
    payload_base64: str = Field(min_length=1)
    genome_build: Literal["GRCh37/hg19", "GRCh38/hg38", "unknown"] = "unknown"
    confirmation: bool
    selected_loci: list[str] = Field(default_factory=list, max_length=500)


class GeneticsReviewRequest(APIModel):
    status: Literal["reviewed", "dismissed", "unsupported", "conflicting"]
    reason: str | None = Field(default=None, max_length=1000)


class GeneticsResearchRequest(APIModel):
    mode: Literal["evidence", "explore"]
    question: str = Field(min_length=1, max_length=2000)
    finding_ids: list[str] = Field(min_length=1, max_length=100)
    canonical_records: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    second_person_id: str | None = None


class GeneticsComparisonRequest(APIModel):
    person_b_id: str = Field(min_length=1)


class GeneticsExportRequest(APIModel):
    confirmation: bool
    include_research: bool = False


class ErrorResponse(APIModel):
    error: dict[str, Any]
