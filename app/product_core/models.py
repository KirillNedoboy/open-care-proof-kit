from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal["manual_entry", "plain_text"]
FactType = Literal["medication"]
CandidateStatus = Literal["pending", "confirmed", "corrected", "rejected"]


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def isoformat_utc(value: datetime) -> str:
    return ensure_utc_datetime(value).isoformat()


def parse_utc_datetime(value: str) -> datetime:
    return ensure_utc_datetime(datetime.fromisoformat(value))


def normalize_medication_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


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


class CandidateFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    fact_type: FactType = "medication"
    status: CandidateStatus = "pending"
    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    schedule_text: str | None = None
    note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    predecessor_candidate_id: str | None = None

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc_datetime(value)

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateFact:
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.normalized_name != normalize_medication_name(self.display_name):
            raise ValueError("normalized_name must match display_name")
        if self.status == "pending" and self.reviewed_at is not None:
            raise ValueError("pending candidate cannot have reviewed_at")
        if self.status != "pending" and self.reviewed_at is None:
            raise ValueError("reviewed candidate must have reviewed_at")
        if self.predecessor_candidate_id == self.id:
            raise ValueError("candidate cannot be its own predecessor")
        return self


class CanonicalMedicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    schedule_text: str | None = None
    note: str | None = None
    confirmed_at: datetime
    is_active: bool

    @field_validator("confirmed_at")
    @classmethod
    def validate_confirmed_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def validate_name(self) -> CanonicalMedicationRecord:
        if self.normalized_name != normalize_medication_name(self.display_name):
            raise ValueError("normalized_name must match display_name")
        return self


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    canonical_record_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
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
