from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.family_access.policy import CAREGIVER_OPTIONAL_SCOPES

MAX_ID_LENGTH = 128
MAX_DISPLAY_NAME_LENGTH = 200
MAX_USERNAME_LENGTH = 128
MAX_FAMILY_PEOPLE = 100


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _clean_text(value: str, *, field_name: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise ValueError(f"{field_name} is invalid")
    if any(unicodedata.category(character) == "Cc" for character in cleaned):
        raise ValueError(f"{field_name} contains control characters")
    return cleaned


def _identifier(value: str) -> str:
    return _clean_text(value, field_name="identifier", max_length=MAX_ID_LENGTH)


class EmptyRequest(APIModel):
    pass


class BootstrapRequest(APIModel):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    password: str = Field(min_length=12, max_length=1024)
    person_ids: list[str] = Field(default_factory=list, max_length=MAX_FAMILY_PEOPLE)
    own_person_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)
    confirm_full_owner_access: bool = Field(default=False, strict=True)
    bootstrap_secret: str | None = Field(default=None, max_length=1024)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _clean_text(value, field_name="username", max_length=MAX_USERNAME_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _clean_text(value, field_name="display_name", max_length=MAX_DISPLAY_NAME_LENGTH)

    @field_validator("person_ids")
    @classmethod
    def validate_people(cls, values: list[str]) -> list[str]:
        cleaned = [_identifier(value) for value in values]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("person_ids must be unique")
        return cleaned

    @field_validator("own_person_id")
    @classmethod
    def validate_own_person(cls, value: str | None) -> str | None:
        return None if value is None else _identifier(value)


class LoginRequest(APIModel):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    password: str = Field(min_length=1, max_length=1024)


class RegistrationRequest(APIModel):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _clean_text(value, field_name="username", max_length=MAX_USERNAME_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _clean_text(value, field_name="display_name", max_length=MAX_DISPLAY_NAME_LENGTH)


class PasswordChangeRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class ActivePersonRequest(APIModel):
    person_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)

    @field_validator("person_id")
    @classmethod
    def validate_person(cls, value: str | None) -> str | None:
        return None if value is None else _identifier(value)


class PersonCreateRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    date_of_birth: date | None = None
    confirm_owner_assignment: bool = Field(default=False, strict=True)
    link_as_own: bool = Field(default=False, strict=True)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _clean_text(value, field_name="display_name", max_length=MAX_DISPLAY_NAME_LENGTH)


class FamilyCreateRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _clean_text(value, field_name="display_name", max_length=MAX_DISPLAY_NAME_LENGTH)


class MembershipCreateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)

    @field_validator("person_id")
    @classmethod
    def validate_person(cls, value: str) -> str:
        return _identifier(value)


class RelationshipCreateRequest(APIModel):
    person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    related_person_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    relationship_type: Literal[
        "parent", "child", "spouse", "partner", "sibling", "guardian", "dependent", "other"
    ]

    @field_validator("person_id", "related_person_id")
    @classmethod
    def validate_person(cls, value: str) -> str:
        return _identifier(value)


class AssignmentCreateRequest(APIModel):
    recipient_actor_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    role: Literal["owner", "caregiver"]
    optional_scopes: set[str] = Field(default_factory=set, max_length=20)
    confirm_full_owner_access: bool = Field(default=False, strict=True)

    @field_validator("recipient_actor_id")
    @classmethod
    def validate_actor(cls, value: str) -> str:
        return _identifier(value)

    @model_validator(mode="after")
    def validate_scopes(self) -> AssignmentCreateRequest:
        if self.role == "caregiver" and not self.optional_scopes <= CAREGIVER_OPTIONAL_SCOPES:
            raise ValueError("caregiver scope is not permitted")
        return self


class AssignmentReviseRequest(APIModel):
    optional_scopes: set[str] = Field(default_factory=set, max_length=20)
    policy_generation: (
        Literal["family-access-v1", "family-access-v2", "family-access-v3"] | None
    ) = None

    @field_validator("optional_scopes")
    @classmethod
    def validate_scopes(cls, value: set[str]) -> set[str]:
        if not value <= CAREGIVER_OPTIONAL_SCOPES:
            raise ValueError("caregiver scope is not permitted")
        return value


class AssignmentUpgradeRequest(APIModel):
    confirm_full_owner_access: bool = Field(default=False, strict=True)


class InvitationCreateRequest(APIModel):
    role: Literal["owner", "caregiver"]
    optional_scopes: set[str] = Field(default_factory=set, max_length=20)
    expires_at: datetime
    confirm_full_owner_access: bool = Field(default=False, strict=True)

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_scopes(self) -> InvitationCreateRequest:
        if self.role == "caregiver" and not self.optional_scopes <= CAREGIVER_OPTIONAL_SCOPES:
            raise ValueError("caregiver scope is not permitted")
        return self


class InvitationSecretRequest(APIModel):
    secret: str = Field(min_length=1, max_length=512)


class InvitationRegisterRequest(InvitationSecretRequest):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    password: str = Field(min_length=12, max_length=1024)
    confirm_full_owner_access: bool = Field(default=False, strict=True)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _clean_text(value, field_name="username", max_length=MAX_USERNAME_LENGTH)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _clean_text(value, field_name="display_name", max_length=MAX_DISPLAY_NAME_LENGTH)


class InvitationAcceptRequest(InvitationSecretRequest):
    confirm_full_owner_access: bool = Field(default=False, strict=True)
