"""D2.2 policy tests: frozen v1-v3 generations, v4 scope sets, no silent expansion.

Pure-policy tests plus one cheap end-to-end authority proof through the real
``ProductCoreAccess`` candidate-review gate (app/product_core/access.py)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.family_access.policy import (
    CAREGIVER_BASE_SCOPES,
    CAREGIVER_BASE_SCOPES_V1,
    CAREGIVER_BASE_SCOPES_V2,
    CAREGIVER_BASE_SCOPES_V3,
    CAREGIVER_BASE_SCOPES_V4,
    CAREGIVER_OPTIONAL_SCOPES,
    CAREGIVER_OPTIONAL_SCOPES_V1,
    CAREGIVER_OPTIONAL_SCOPES_V2,
    CAREGIVER_OPTIONAL_SCOPES_V3,
    CAREGIVER_OPTIONAL_SCOPES_V4,
    OWNER_SCOPES,
    OWNER_SCOPES_V1,
    OWNER_SCOPES_V2,
    OWNER_SCOPES_V3,
    OWNER_SCOPES_V4,
    POLICY_VERSION,
    V1_POLICY_VERSION,
    V2_POLICY_VERSION,
    V3_POLICY_VERSION,
    PersonAccessPolicy,
    infer_generation,
    valid_role_scopes,
)
from app.family_access.service import FamilyAccessService
from app.product_core.access import ProductCoreAccess
from app.product_core.errors import ScopeForbiddenError
from app.product_core.models import Person, ProcedureCandidateInput
from app.product_core.services import FactLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase

TS = "2026-08-09T10:00:00+00:00"

V2_SCOPES = frozenset({"condition.read", "condition.write", "lab.read", "lab.write"})
V3_SCOPES = frozenset({"document.read", "document.write"})
V4_READ_SCOPES = frozenset({"procedure.read", "recommendation.read", "follow_up.read"})
V4_WRITE_SCOPES = frozenset(
    {"procedure.write", "recommendation.write", "follow_up.write"}
)
V4_SCOPES = V4_READ_SCOPES | V4_WRITE_SCOPES

#: Verbatim v1 literals (frozen since the pre-P1 model; v4 must not mutate them).
OWNER_V1_LITERALS = frozenset(
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
CAREGIVER_BASE_V1_LITERALS = frozenset(
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
CAREGIVER_OPTIONAL_V1_LITERALS = frozenset(
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


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"d22p-{self.value}"


def test_v1_v2_v3_scope_sets_are_frozen() -> None:
    for v1_set in (
        OWNER_SCOPES_V1,
        CAREGIVER_BASE_SCOPES_V1,
        CAREGIVER_OPTIONAL_SCOPES_V1,
    ):
        assert not v1_set & V2_SCOPES
        assert not v1_set & V3_SCOPES
        assert not v1_set & V4_SCOPES
    # v1 equals its frozen defining literals (unmutated by the v4 addition).
    assert OWNER_SCOPES_V1 == OWNER_V1_LITERALS
    assert CAREGIVER_BASE_SCOPES_V1 == CAREGIVER_BASE_V1_LITERALS
    assert CAREGIVER_OPTIONAL_SCOPES_V1 == CAREGIVER_OPTIONAL_V1_LITERALS
    # v2 == v1 | record families
    assert OWNER_SCOPES_V2 == OWNER_SCOPES_V1 | V2_SCOPES
    assert CAREGIVER_BASE_SCOPES_V1 | {
        "condition.read",
        "lab.read",
    } == CAREGIVER_BASE_SCOPES_V2
    assert CAREGIVER_OPTIONAL_SCOPES_V1 | {
        "condition.write",
        "lab.write",
    } == CAREGIVER_OPTIONAL_SCOPES_V2
    # v3 == v2 | documents
    assert OWNER_SCOPES_V3 == OWNER_SCOPES_V2 | V3_SCOPES
    assert CAREGIVER_BASE_SCOPES_V2 | {"document.read"} == CAREGIVER_BASE_SCOPES_V3
    assert CAREGIVER_OPTIONAL_SCOPES_V2 | {"document.write"} == CAREGIVER_OPTIONAL_SCOPES_V3
    # v3 still carries no v4 capability
    assert not OWNER_SCOPES_V3 & V4_SCOPES
    assert not CAREGIVER_BASE_SCOPES_V3 & V4_SCOPES
    assert not CAREGIVER_OPTIONAL_SCOPES_V3 & V4_SCOPES


def test_v4_sets_compose_from_v3_and_aliases_point_at_v4() -> None:
    assert OWNER_SCOPES_V4 == OWNER_SCOPES_V3 | V4_SCOPES
    assert CAREGIVER_BASE_SCOPES_V4 == CAREGIVER_BASE_SCOPES_V3 | V4_READ_SCOPES
    # Caregiver base gains reads only: no new write scope may leak into base.
    assert not CAREGIVER_BASE_SCOPES_V4 & V4_WRITE_SCOPES
    assert CAREGIVER_OPTIONAL_SCOPES_V4 == CAREGIVER_OPTIONAL_SCOPES_V3 | V4_WRITE_SCOPES
    assert POLICY_VERSION == "family-access-v4"
    assert OWNER_SCOPES == OWNER_SCOPES_V4
    assert CAREGIVER_BASE_SCOPES == CAREGIVER_BASE_SCOPES_V4
    assert CAREGIVER_OPTIONAL_SCOPES == CAREGIVER_OPTIONAL_SCOPES_V4


def test_infer_generation_reads_only_generation_unique_scopes() -> None:
    assert infer_generation({"procedure.read"}) == POLICY_VERSION
    assert infer_generation({"procedure.write"}) == POLICY_VERSION
    assert infer_generation(frozenset({"follow_up.read", "document.read"})) == POLICY_VERSION
    # A stored v3 set infers v3: no silent expansion into v4.
    assert infer_generation(OWNER_SCOPES_V3) == V3_POLICY_VERSION
    assert infer_generation(OWNER_SCOPES_V2) == V2_POLICY_VERSION
    assert infer_generation(OWNER_SCOPES_V1) == V1_POLICY_VERSION
    assert infer_generation("procedure.read") == V1_POLICY_VERSION
    assert infer_generation(None) == V1_POLICY_VERSION
    assert infer_generation(42) == V1_POLICY_VERSION


def test_valid_role_scopes_across_generations() -> None:
    assert valid_role_scopes("owner", OWNER_SCOPES_V3) is True
    assert valid_role_scopes("owner", OWNER_SCOPES_V4) is True
    # True behavior: a v3 set + one v4 scope infers v4, but an owner must hold
    # the FULL v4 set; a partial v3+v4 mix is invalid, so a stale grant can
    # never gain capabilities by smuggling in one scope.
    assert valid_role_scopes("owner", OWNER_SCOPES_V3 | {"procedure.read"}) is False
    assert valid_role_scopes("caregiver", CAREGIVER_BASE_SCOPES_V4) is True
    assert (
        valid_role_scopes("caregiver", CAREGIVER_BASE_SCOPES_V4 | {"follow_up.write"})
        is True
    )
    # True behavior: v3 base + procedure.write infers v4 and fails the v4
    # containment test — the generation guard prevents silent expansion.
    assert (
        valid_role_scopes("caregiver", CAREGIVER_BASE_SCOPES_V3 | {"procedure.write"})
        is False
    )
    assert valid_role_scopes("stranger", OWNER_SCOPES_V4) is False


def _grant(
    database: SQLiteDatabase,
    *,
    actor_id: str,
    person_id: str,
    scopes: frozenset[str],
) -> None:
    with database.uow() as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            INSERT INTO actors (actor_id, username_normalized, display_name, status, created_at)
            VALUES (?, ?, ?, 'active', ?)
            """,
            (actor_id, actor_id, actor_id, TS),
        )
        uow.connection.execute(
            """
            INSERT INTO person_access_consent_history (
                consent_event_id, event_type, acting_owner_actor_id, recipient_actor_id,
                person_id, role, scopes_json, reason_code, created_at
            ) VALUES (?, 'grant', ?, ?, ?, 'owner', ?, 'bootstrap', ?)
            """,
            (
                f"consent-{actor_id}",
                actor_id,
                actor_id,
                person_id,
                json.dumps(sorted(scopes)),
                TS,
            ),
        )
        uow.connection.execute(
            """
            INSERT INTO person_access_assignments (
                assignment_id, actor_id, person_id, role, scopes_json, consent_event_id,
                granted_by_actor_id, is_active, granted_at
            ) VALUES (?, ?, ?, 'owner', ?, ?, ?, 1, ?)
            """,
            (
                f"assignment-{actor_id}",
                actor_id,
                person_id,
                json.dumps(sorted(scopes)),
                f"consent-{actor_id}",
                actor_id,
                TS,
            ),
        )


def _access(database: SQLiteDatabase, actor_id: str) -> ProductCoreAccess:
    service = FamilyAccessService(
        database,
        clock=FixedClock(datetime(2026, 8, 9, 10, tzinfo=UTC)),
        id_factory=SequenceIds(),
        policy=PersonAccessPolicy(),
    )
    return ProductCoreAccess(
        runtime=SimpleNamespace(database=database),
        family_runtime=SimpleNamespace(service=service),
        authenticated=SimpleNamespace(
            actor=SimpleNamespace(actor_id=actor_id),
            record=SimpleNamespace(active_person_id="person-1"),
            session_token="token",
        ),
    )


def test_stored_v3_owner_grant_cannot_authorize_procedure_write(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    now = datetime(2026, 8, 9, 10, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Profile person-1",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    _grant(database, actor_id="actor-v3", person_id="person-1", scopes=OWNER_SCOPES_V3)
    _grant(database, actor_id="actor-v4", person_id="person-1", scopes=OWNER_SCOPES_V4)

    clock = FixedClock(datetime(2026, 8, 9, 10, tzinfo=UTC))
    ids = SequenceIds()
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = FactLifecycleService(database, clock=clock, id_factory=ids)
    source = sources.register_manual_entry("person-1", "Colonoscopy")
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        fact_type="procedure",
        detail_input=ProcedureCandidateInput(display_name="Colonoscopy"),
    )

    # Direct policy: the v4 scope is outside the v3 assignment's universe.
    policy = PersonAccessPolicy()
    denied = policy.authorize(
        actor_id="actor-v3",
        person_id="person-1",
        required_scope="procedure.write",
        assignment={
            "actor_id": "actor-v3",
            "person_id": "person-1",
            "role": "owner",
            "scopes": OWNER_SCOPES_V3,
            "is_active": True,
        },
    )
    assert denied.allowed is False
    granted = policy.authorize(
        actor_id="actor-v4",
        person_id="person-1",
        required_scope="procedure.write",
        assignment={
            "actor_id": "actor-v4",
            "person_id": "person-1",
            "role": "owner",
            "scopes": OWNER_SCOPES_V4,
            "is_active": True,
        },
    )
    assert granted.allowed is True
    assert granted.reason_code == "scope_granted"

    # Through the real candidate-review gate (fact_type -> procedure.write).
    assert (
        _access(database, "actor-v4").preflight_candidate_review(candidate.id)
        == "person-1"
    )
    try:
        _access(database, "actor-v3").preflight_candidate_review(candidate.id)
    except ScopeForbiddenError:
        pass
    else:
        raise AssertionError("v3 grant must not authorize procedure review")
