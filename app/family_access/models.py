from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AccessRole = Literal["owner", "caregiver"]


@dataclass(frozen=True)
class InvalidStoredScopes:
    pass


@dataclass(frozen=True)
class ActorRecord:
    actor_id: str
    username_normalized: str
    display_name: str
    status: Literal["active", "disabled"]
    created_at: datetime


@dataclass(frozen=True)
class AuthenticatedCredential:
    actor: ActorRecord
    credential_id: str


@dataclass(frozen=True)
class FamilyRecord:
    family_id: str
    display_name: str
    created_by_actor_id: str
    created_at: datetime
    is_archived: bool


@dataclass(frozen=True)
class MembershipRecord:
    membership_id: str
    family_id: str
    person_id: str
    is_active: bool


@dataclass(frozen=True)
class RelationshipRecord:
    relationship_id: str
    family_id: str
    person_id: str
    related_person_id: str
    relationship_type: str
    is_active: bool


@dataclass(frozen=True)
class AssignmentRecord:
    assignment_id: str
    actor_id: str
    person_id: str
    role: AccessRole
    scopes: frozenset[str] | InvalidStoredScopes
    is_active: bool


@dataclass(frozen=True)
class InvitationIssued:
    invitation_id: str
    secret: str
    person_id: str
    role: AccessRole
    scopes: frozenset[str]
    expires_at: datetime


@dataclass(frozen=True)
class InvitationPreview:
    role: AccessRole
    scopes: frozenset[str]
    expires_at: datetime
