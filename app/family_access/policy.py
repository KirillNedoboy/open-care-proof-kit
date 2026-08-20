from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import Literal

#: The current policy generation. New grants use this generation; the
#: generation under which an assignment was granted is inferred from its
#: stored scopes (see ``infer_generation``), so old consent events are never
#: rewritten and never silently gain new capabilities.
POLICY_VERSION = "family-access-v3"
V1_POLICY_VERSION = "family-access-v1"
V2_POLICY_VERSION = "family-access-v2"

# --------------------------------------------------------------------------- #
# family-access-v1: frozen verbatim from the pre-P1 scope model.
# Assignments granted under v1 keep EXACTLY this authority forever; they never
# inherit the v2 record-family scopes.
# --------------------------------------------------------------------------- #
OWNER_SCOPES_V1 = frozenset(
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

CAREGIVER_BASE_SCOPES_V1 = frozenset(
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

CAREGIVER_OPTIONAL_SCOPES_V1 = frozenset(
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

# --------------------------------------------------------------------------- #
# family-access-v2: v1 plus explicit record-family capabilities. These scope
# strings exist ONLY in v2 sets; any stored assignment containing them is
# inferred as v2 and validated against the v2 sets.
# --------------------------------------------------------------------------- #
RECORD_READ_SCOPES = frozenset({"condition.read", "lab.read"})
RECORD_WRITE_SCOPES = frozenset({"condition.write", "lab.write"})
V2_ONLY_SCOPES = RECORD_READ_SCOPES | RECORD_WRITE_SCOPES

OWNER_SCOPES_V2 = OWNER_SCOPES_V1 | RECORD_READ_SCOPES | RECORD_WRITE_SCOPES
CAREGIVER_BASE_SCOPES_V2 = CAREGIVER_BASE_SCOPES_V1 | RECORD_READ_SCOPES
CAREGIVER_OPTIONAL_SCOPES_V2 = CAREGIVER_OPTIONAL_SCOPES_V1 | RECORD_WRITE_SCOPES

# --------------------------------------------------------------------------- #
# family-access-v3: explicit document authority. v1/v2 sets above are frozen.
# --------------------------------------------------------------------------- #
V3_ONLY_SCOPES = frozenset({"document.read", "document.write"})
OWNER_SCOPES_V3 = OWNER_SCOPES_V2 | V3_ONLY_SCOPES
CAREGIVER_BASE_SCOPES_V3 = CAREGIVER_BASE_SCOPES_V2 | {"document.read"}
CAREGIVER_OPTIONAL_SCOPES_V3 = CAREGIVER_OPTIONAL_SCOPES_V2 | {"document.write"}

# Current-generation aliases: new grants and display surfaces use these.
OWNER_SCOPES = OWNER_SCOPES_V3
CAREGIVER_BASE_SCOPES = CAREGIVER_BASE_SCOPES_V3
CAREGIVER_OPTIONAL_SCOPES = CAREGIVER_OPTIONAL_SCOPES_V3

_GENERATION_SETS: dict[str, tuple[frozenset[str], frozenset[str], frozenset[str]]] = {
    V1_POLICY_VERSION: (
        OWNER_SCOPES_V1,
        CAREGIVER_BASE_SCOPES_V1,
        CAREGIVER_OPTIONAL_SCOPES_V1,
    ),
    V2_POLICY_VERSION: (
        OWNER_SCOPES_V2,
        CAREGIVER_BASE_SCOPES_V2,
        CAREGIVER_OPTIONAL_SCOPES_V2,
    ),
    POLICY_VERSION: (
        OWNER_SCOPES_V3,
        CAREGIVER_BASE_SCOPES_V3,
        CAREGIVER_OPTIONAL_SCOPES_V3,
    ),
}


def infer_generation(scopes: object) -> str:
    """Infer a grant generation only from generation-unique stored scopes."""
    if not isinstance(scopes, (set, frozenset, list, tuple)):
        return V1_POLICY_VERSION
    if not all(isinstance(scope, str) for scope in scopes):
        return V1_POLICY_VERSION
    normalized = frozenset(scopes)
    if normalized & V3_ONLY_SCOPES:
        return POLICY_VERSION
    if normalized & V2_ONLY_SCOPES:
        return V2_POLICY_VERSION
    return V1_POLICY_VERSION


def valid_role_scopes(role: object, scopes: object) -> bool:
    if not isinstance(scopes, (set, frozenset, list, tuple)):
        return False
    if not all(isinstance(scope, str) for scope in scopes):
        return False
    normalized = frozenset(scopes)
    generation = infer_generation(normalized)
    owner_scopes, base_scopes, optional_scopes = _GENERATION_SETS[generation]
    if role == "owner":
        return normalized == owner_scopes
    if role == "caregiver":
        return normalized >= base_scopes and normalized <= base_scopes | optional_scopes
    return False


def build_scopes(
    role: Literal["owner", "caregiver"],
    optional_scopes: Set[str] | None = None,
    *,
    generation: str = POLICY_VERSION,
) -> frozenset[str]:
    """Build the scope set for a NEW grant under the chosen generation.

    New grants default to the current generation; an explicit generation is
    honored only for controlled upgrade/revision paths that record a new
    consent event.
    """
    if generation not in _GENERATION_SETS:
        raise ValueError("unsupported policy generation")
    _owner_scopes, base_scopes, optional_scope_set = _GENERATION_SETS[generation]
    requested = frozenset(optional_scopes or ())
    if role == "owner":
        return _owner_scopes
    if role != "caregiver":
        raise ValueError("unsupported access role")
    disallowed = requested - optional_scope_set
    if disallowed:
        raise ValueError("caregiver scope is not permitted")
    return base_scopes | requested


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
        if assignment is None:
            return PolicyDecision(allowed=False)
        role = assignment.get("role")
        scopes_value = assignment.get("scopes")
        if not valid_role_scopes(role, scopes_value):
            return PolicyDecision(allowed=False, reason_code="invalid_assignment_scopes")
        assert isinstance(scopes_value, (set, frozenset, list, tuple))
        scopes = frozenset(scopes_value)
        generation = infer_generation(scopes)
        owner_scopes, _base_scopes, _optional_scopes = _GENERATION_SETS[generation]
        if required_scope not in owner_scopes:
            # A scope string outside the assignment's generation's universe is
            # never satisfiable (e.g. condition.read for a v1 assignment).
            return PolicyDecision(allowed=False)
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
