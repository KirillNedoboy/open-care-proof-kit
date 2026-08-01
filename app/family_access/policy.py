from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import Literal

POLICY_VERSION = "family-access-v1"

OWNER_SCOPES = frozenset(
    {
        "person.read",
        "person.update",
        "source.read",
        "source.write",
        "candidate.read",
        "candidate.review",
        "medication.read",
        "medication.write",
        "timeline.read",
        "visit.read",
        "visit.write",
        "brief.read",
        "brief.write",
        "brief.export",
        "vault.export",
        "relationship.read",
        "relationship.manage",
        "access.read",
        "access.manage",
        "chat.use",
    }
)

CAREGIVER_BASE_SCOPES = frozenset(
    {
        "person.read",
        "source.read",
        "candidate.read",
        "medication.read",
        "timeline.read",
        "visit.read",
        "brief.read",
        "relationship.read",
        "chat.use",
    }
)

CAREGIVER_OPTIONAL_SCOPES = frozenset(
    {
        "source.write",
        "candidate.review",
        "medication.write",
        "visit.write",
        "brief.write",
        "brief.export",
        "vault.export",
    }
)

ALL_SCOPES = OWNER_SCOPES


def valid_role_scopes(role: object, scopes: object) -> bool:
    if not isinstance(scopes, (set, frozenset, list, tuple)):
        return False
    if not all(isinstance(scope, str) for scope in scopes):
        return False
    normalized = frozenset(scopes)
    if role == "owner":
        return normalized == OWNER_SCOPES
    if role == "caregiver":
        return (
            normalized >= CAREGIVER_BASE_SCOPES
            and normalized <= CAREGIVER_BASE_SCOPES | CAREGIVER_OPTIONAL_SCOPES
        )
    return False


def build_scopes(
    role: Literal["owner", "caregiver"],
    optional_scopes: Set[str] | None = None,
) -> frozenset[str]:
    requested = frozenset(optional_scopes or ())
    if role == "owner":
        return OWNER_SCOPES
    if role != "caregiver":
        raise ValueError("unsupported access role")
    disallowed = requested - CAREGIVER_OPTIONAL_SCOPES
    if disallowed:
        raise ValueError("caregiver scope is not permitted")
    return CAREGIVER_BASE_SCOPES | requested


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    policy_version: str = POLICY_VERSION
    reason_code: str = "person_access_denied"


class PersonAccessPolicy:
    version = POLICY_VERSION

    def authorize(
        self,
        *,
        actor_id: str,
        person_id: str,
        required_scope: str,
        assignment: Mapping[str, object] | None,
        is_installation_admin: bool = False,
        has_family_membership: bool = False,
        has_relationship: bool = False,
        has_own_person_link: bool = False,
    ) -> PolicyDecision:
        del is_installation_admin, has_family_membership, has_relationship, has_own_person_link
        if required_scope not in ALL_SCOPES or assignment is None:
            return PolicyDecision(allowed=False)
        role = assignment.get("role")
        scopes_value = assignment.get("scopes")
        if not valid_role_scopes(role, scopes_value):
            return PolicyDecision(allowed=False, reason_code="invalid_assignment_scopes")
        assert isinstance(scopes_value, (set, frozenset, list, tuple))
        scopes = frozenset(scopes_value)
        matches = (
            assignment.get("actor_id") == actor_id
            and assignment.get("person_id") == person_id
            and assignment.get("is_active") is True
            and required_scope in scopes
        )
        return PolicyDecision(
            allowed=matches,
            reason_code="scope_granted" if matches else "person_access_denied",
        )
