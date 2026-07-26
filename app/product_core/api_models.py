from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.product_core.models import ensure_utc_datetime

CandidateStatus = Literal["pending", "confirmed", "corrected", "rejected"]

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


class MedicationCandidateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    source_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    schedule_text: str | None = Field(default=None, max_length=MAX_SCHEDULE_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)

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


class EmptyActionRequest(APIModel):
    pass


class CorrectCandidateRequest(APIModel):
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


class VisitBriefGenerateRequest(APIModel):
    visit_title: str = Field(min_length=1, max_length=MAX_VISIT_TITLE_LENGTH)
    visit_purpose: str | None = Field(default=None, max_length=MAX_VISIT_TITLE_LENGTH)
    scheduled_date: str | None = Field(default=None, max_length=MAX_VISIT_TITLE_LENGTH)
    generated_at: datetime
    selected_record_ids: list[
        Annotated[str, Field(min_length=1, max_length=MAX_ID_LENGTH)]
    ] | None = Field(
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


class SourceResponse(APIModel):
    source_id: str
    person_id: str
    source_type: Literal["manual_entry", "plain_text"]
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime


class SourceRegistrationResponse(APIModel):
    created: bool
    source: SourceResponse


class CandidateResponse(APIModel):
    id: str
    person_id: str
    source_id: str
    fact_type: Literal["medication"]
    status: CandidateStatus
    display_name: str
    schedule_text: str | None
    note: str | None
    created_at: datetime
    reviewed_at: datetime | None
    predecessor_candidate_id: str | None


class CandidateListResponse(APIModel):
    candidates: list[CandidateResponse]


class CanonicalMedicationResponse(APIModel):
    id: str
    person_id: str
    candidate_id: str
    source_id: str
    display_name: str
    schedule_text: str | None
    note: str | None
    confirmed_at: datetime
    is_active: bool


class CanonicalMedicationListResponse(APIModel):
    medications: list[CanonicalMedicationResponse]


class TimelineEventResponse(APIModel):
    id: str
    person_id: str
    canonical_record_id: str
    source_id: str
    event_type: str
    event_at: datetime
    title: str


class TimelineResponse(APIModel):
    events: list[TimelineEventResponse]


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


class ErrorResponse(APIModel):
    error: dict[str, Any]
