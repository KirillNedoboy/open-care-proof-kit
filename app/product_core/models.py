from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal["manual_entry", "plain_text"]
FactType = Literal["medication", "condition", "lab"]
CandidateStatus = Literal["pending", "confirmed", "corrected", "rejected", "unsupported"]
VisitBriefRevisionOrigin = Literal[
    "deterministic_generation", "user_edit", "regeneration"
]
VisitBriefState = Literal["current", "stale", "unavailable"]


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def isoformat_utc(value: datetime) -> str:
    return ensure_utc_datetime(value).isoformat()


def parse_utc_datetime(value: str) -> datetime:
    return ensure_utc_datetime(datetime.fromisoformat(value))


def normalize_medication_name(value: str) -> str:
    """Whitespace-normalize + casefold a display name for stable identity matching.

    The same normalization applies to medication, condition, and lab display
    names; it is used only for identity/display matching, never for clinical
    normalization.
    """
    return re.sub(r"\s+", " ", value).strip().casefold()


normalize_fact_name = normalize_medication_name


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    source_type: SourceType
    relative_path: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)
    created_at: datetime
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    date_of_birth: date | None = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be empty")
        return cleaned

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class MedicationCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    schedule_text: str | None = None
    note: str | None = None

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be empty")
        return cleaned


class ConditionCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    status_text: str | None = None
    onset_date: date | None = None
    note: str | None = None

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be empty")
        return cleaned


class LabCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str = Field(min_length=1)
    result_text: str = ""
    unit_text: str | None = None
    reference_range_text: str | None = None
    observed_date: date | None = None
    source_flag_text: str | None = None
    note: str | None = None

    @field_validator("test_name")
    @classmethod
    def trim_test_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("test_name must not be empty")
        return cleaned


class MedicationCandidateDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    schedule_text: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_name(self) -> MedicationCandidateDetail:
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.normalized_name != normalize_medication_name(self.display_name):
            raise ValueError("normalized_name must match display_name")
        return self


class ConditionCandidateDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    status_text: str | None = None
    onset_date: date | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_name(self) -> ConditionCandidateDetail:
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.normalized_name != normalize_medication_name(self.display_name):
            raise ValueError("normalized_name must match display_name")
        return self


class LabCandidateDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str = Field(min_length=1)
    normalized_test_name: str = Field(min_length=1)
    result_text: str = ""
    unit_text: str | None = None
    reference_range_text: str | None = None
    observed_date: date | None = None
    source_flag_text: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def validate_name(self) -> LabCandidateDetail:
        if not self.test_name.strip():
            raise ValueError("test_name must not be empty")
        if self.normalized_test_name != normalize_medication_name(self.test_name):
            raise ValueError("normalized_test_name must match test_name")
        return self


CandidateDetail = MedicationCandidateDetail | ConditionCandidateDetail | LabCandidateDetail


class CandidateFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    fact_type: FactType
    status: CandidateStatus = "pending"
    detail: CandidateDetail
    created_at: datetime
    reviewed_at: datetime | None = None
    predecessor_candidate_id: str | None = None
    provenance_locator: dict[str, Any] | None = None

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc_datetime(value)

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateFact:
        if self.status == "pending" and self.reviewed_at is not None:
            raise ValueError("pending candidate cannot have reviewed_at")
        if self.status != "pending" and self.reviewed_at is None:
            raise ValueError("reviewed candidate must have reviewed_at")
        if self.predecessor_candidate_id == self.id:
            raise ValueError("candidate cannot be its own predecessor")
        if not _detail_matches_fact_type(self.fact_type, self.detail):
            raise ValueError("detail does not match fact_type")
        return self

    @property
    def display_name(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.display_name
        if isinstance(detail, ConditionCandidateDetail):
            return detail.display_name
        return None

    @property
    def normalized_name(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.normalized_name
        if isinstance(detail, ConditionCandidateDetail):
            return detail.normalized_name
        return None

    @property
    def schedule_text(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.schedule_text
        return None

    @property
    def note(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.note
        if isinstance(detail, ConditionCandidateDetail):
            return detail.note
        if isinstance(detail, LabCandidateDetail):
            return detail.note
        return None


class CanonicalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    fact_type: FactType
    detail: CandidateDetail
    confirmed_at: datetime
    is_active: bool
    superseded_by_record_id: str | None = None
    provenance_locator: dict[str, object] | None = None
    predecessor_candidate_id: str | None = None

    @field_validator("confirmed_at")
    @classmethod
    def validate_confirmed_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def validate_record(self) -> CanonicalRecord:
        if not _detail_matches_fact_type(self.fact_type, self.detail):
            raise ValueError("detail does not match fact_type")
        if self.superseded_by_record_id == self.id:
            raise ValueError("record cannot supersede itself")
        if self.is_active and self.superseded_by_record_id is not None:
            raise ValueError("active record cannot be superseded")
        if not self.is_active and self.superseded_by_record_id is None:
            raise ValueError("superseded record must record its replacement")
        return self

    @property
    def display_name(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.display_name
        if isinstance(detail, ConditionCandidateDetail):
            return detail.display_name
        return None

    @property
    def normalized_name(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.normalized_name
        if isinstance(detail, ConditionCandidateDetail):
            return detail.normalized_name
        return None

    @property
    def schedule_text(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.schedule_text
        return None

    @property
    def note(self) -> str | None:
        detail = self.detail
        if isinstance(detail, MedicationCandidateDetail):
            return detail.note
        if isinstance(detail, ConditionCandidateDetail):
            return detail.note
        if isinstance(detail, LabCandidateDetail):
            return detail.note
        return None


# Medication-compatible alias: the generic canonical record is the single
# canonical truth; the old name is retained only for import compatibility.
CanonicalMedicationRecord = CanonicalRecord


def _detail_matches_fact_type(fact_type: str, detail: object) -> bool:
    if fact_type == "medication":
        return isinstance(detail, MedicationCandidateDetail)
    if fact_type == "condition":
        return isinstance(detail, ConditionCandidateDetail)
    if fact_type == "lab":
        return isinstance(detail, LabCandidateDetail)
    return False


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    canonical_record_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    fact_type: FactType
    event_type: str = Field(min_length=1)
    event_at: datetime
    title: str = Field(min_length=1)

    @field_validator("event_at")
    @classmethod
    def validate_event_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class Visit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visit_id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    specialist: str | None = None
    scheduled_date: date | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    position: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class PersistedVisitBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    current_revision_id: str | None = None
    current_revision_number: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitBriefEvidenceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_record_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    snapshot: dict[str, Any]


class PersistedVisitBriefRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    origin: VisitBriefRevisionOrigin
    parent_revision_id: str | None = None
    content_schema_version: int = Field(ge=1)
    render_version: int = Field(ge=1)
    content: dict[str, Any]
    rendered_markdown: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitBriefStaleness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: VisitBriefState
    reasons: list[str] = Field(default_factory=list)


class VisitBriefAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_event_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    brief_id: str | None = None
    revision_number: int | None = Field(default=None, ge=1)
    action: Literal[
        "initialize",
        "deterministic_generation",
        "regeneration",
        "user_edit",
        "restore",
        "export",
        "concurrency_conflict",
    ]
    involved_resource_ids: list[str] = Field(default_factory=list)
    outcome: Literal["succeeded", "rejected"]
    reason_code: str | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str = Field(min_length=1)
    visit_title: str = Field(min_length=1)
    visit_purpose: str = Field(min_length=1)
    generated_at: datetime
    scheduled_date: str | None = None
    selected_record_ids: list[str] | None = None

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class VisitBriefMedication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    schedule_text: str | None
    note: str | None
    source_id: str = Field(min_length=1)


class VisitBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str = Field(min_length=1)
    visit_title: str = Field(min_length=1)
    visit_purpose: str = Field(min_length=1)
    scheduled_date: str | None
    generated_at: datetime
    records: list[VisitBriefMedication]
    source_references: list[str]
    markdown: str = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)
