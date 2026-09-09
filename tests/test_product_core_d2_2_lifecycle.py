"""D2.2 lifecycle tests: confirm/correct/reject/unsupported for the new
procedure/recommendation/follow-up families, neutral timeline titles, no
automatic canonicalization, wrong-person isolation, and candidate fingerprint
determinism."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.family_access.policy import OWNER_SCOPES_V4, PersonAccessPolicy
from app.family_access.service import FamilyAccessService
from app.product_core.access import ProductCoreAccess
from app.product_core.document_fact_extraction import (
    FollowUpSuggestion,
    ProcedureSuggestion,
    _detail_payload,
    _fingerprint,
)
from app.product_core.errors import (
    CandidateNotFoundError,
    InvalidTransitionError,
)
from app.product_core.models import (
    FollowUpCandidateInput,
    MedicationCandidateInput,
    Person,
    ProcedureCandidateInput,
    RecommendationCandidateInput,
    normalize_fact_name,
)
from app.product_core.services import FactLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase

TS = "2026-08-09T10:00:00+00:00"


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self, *values: str) -> None:
        self.values = iter(values)

    def __call__(self) -> str:
        return next(self.values)


def make_services(
    tmp_path: Path,
    ids: SequenceIds,
    *person_ids: str,
) -> tuple[SQLiteDatabase, SourceService, FactLifecycleService]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    now = datetime(2026, 8, 9, 10, tzinfo=UTC)
    with database.uow() as uow:
        for person_id in person_ids or ("person-1",):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=f"Profile {person_id}",
                    created_at=now,
                    updated_at=now,
                    is_active=True,
                )
            )
    clock = FixedClock(now)
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = FactLifecycleService(database, clock=clock, id_factory=ids)
    return database, sources, lifecycle


def _create_pending(
    sources: SourceService,
    lifecycle: FactLifecycleService,
    person_id: str,
    fact_type: str,
    detail_input: object,
    source_name: str,
) -> str:
    # schema_version 1 manual payloads carry the name under medication.name;
    # with no source_reader wired the locator path is not content-validated,
    # matching tests/test_product_core_lifecycle.py's fixture convention.
    source = sources.register_manual_entry(person_id, source_name)
    candidate = lifecycle.create_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type=fact_type,
        detail_input=detail_input,
    )
    return candidate.id


def test_confirm_procedure_writes_generic_and_detail_rows_with_recorded_title(
    tmp_path: Path,
) -> None:
    ids = SequenceIds("source-1", "candidate-1", "canonical-1", "event-1")
    database, sources, lifecycle = make_services(tmp_path, ids)
    candidate_id = _create_pending(
        sources,
        lifecycle,
        "person-1",
        "procedure",
        ProcedureCandidateInput(display_name="Colonoscopy", date_text="March 2026"),
        "Colonoscopy",
    )

    canonical = lifecycle.confirm(candidate_id)

    assert canonical.fact_type == "procedure"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_procedure_details WHERE record_id = ?",
            (canonical.id,),
        ).fetchone()[0] == 1
    events = lifecycle.list_timeline("person-1")
    assert [event.title for event in events] == ["Procedure recorded: Colonoscopy"]


def test_confirm_long_recommendation_truncates_title_ellipsis(tmp_path: Path) -> None:
    long_instruction = (
        "Continue the current management plan exactly as written and review it "
        "again with the clinic team at the next scheduled appointment"
    )
    assert len(long_instruction) > 80
    ids = SequenceIds("source-1", "candidate-1", "canonical-1", "event-1")
    database, sources, lifecycle = make_services(tmp_path, ids)
    candidate_id = _create_pending(
        sources,
        lifecycle,
        "person-1",
        "recommendation",
        RecommendationCandidateInput(instruction_text=long_instruction),
        long_instruction,
    )

    lifecycle.confirm(candidate_id)

    events = lifecycle.list_timeline("person-1")
    assert len(events) == 1
    title = events[0].title
    prefix = "Recommendation recorded: "
    assert title.startswith(prefix)
    body = title.removeprefix(prefix)
    assert body.endswith("…")
    assert len(body) == 80  # 79 characters plus the ellipsis marker
    assert long_instruction.startswith(body[:-1])
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_recommendation_details"
        ).fetchone()[0] == 1


def test_confirm_follow_up_title_uses_action_text(tmp_path: Path) -> None:
    ids = SequenceIds("source-1", "candidate-1", "canonical-1", "event-1")
    _, sources, lifecycle = make_services(tmp_path, ids)
    candidate_id = _create_pending(
        sources,
        lifecycle,
        "person-1",
        "follow_up",
        FollowUpCandidateInput(action_text="Repeat labs", timing_text="in 3 months"),
        "Repeat labs",
    )

    lifecycle.confirm(candidate_id)

    events = lifecycle.list_timeline("person-1")
    assert [event.title for event in events] == ["Follow-up recorded: Repeat labs"]


def test_medication_confirm_title_regression_pin(tmp_path: Path) -> None:
    ids = SequenceIds("source-1", "candidate-1", "canonical-1", "event-1")
    _, sources, lifecycle = make_services(tmp_path, ids)
    candidate_id = _create_pending(
        sources,
        lifecycle,
        "person-1",
        "medication",
        MedicationCandidateInput(display_name="Aspirin"),
        "Aspirin",
    )

    lifecycle.confirm(candidate_id)

    events = lifecycle.list_timeline("person-1")
    assert [event.title for event in events] == ["Medication confirmed: Aspirin"]
    assert candidate_id is not None


@pytest.mark.parametrize(
    ("fact_type", "original_input", "replacement_input", "name"),
    [
        (
            "procedure",
            ProcedureCandidateInput(display_name="Biopsy"),
            ProcedureCandidateInput(display_name="Excision"),
            "Biopsy",
        ),
        (
            "recommendation",
            RecommendationCandidateInput(instruction_text="Rest for a week"),
            RecommendationCandidateInput(instruction_text="Rest for two weeks"),
            "Rest for a week",
        ),
        (
            "follow_up",
            FollowUpCandidateInput(action_text="See cardiology"),
            FollowUpCandidateInput(action_text="See neurology"),
            "See cardiology",
        ),
    ],
)
def test_correction_lineage_for_new_types(
    tmp_path: Path,
    fact_type: str,
    original_input: object,
    replacement_input: object,
    name: str,
) -> None:
    ids = SequenceIds("source-1", "candidate-1", "replacement-1")
    database, sources, lifecycle = make_services(tmp_path, ids)
    candidate_id = _create_pending(sources, lifecycle, "person-1", fact_type, original_input, name)

    replacement = lifecycle.correct(candidate_id, detail_input=replacement_input)

    original = lifecycle.get_candidate(candidate_id)
    assert original.status == "corrected"
    assert original.reviewed_at is not None
    assert replacement.status == "pending"
    assert replacement.fact_type == fact_type
    assert replacement.predecessor_candidate_id == candidate_id
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_facts WHERE predecessor_candidate_id = ?",
            (candidate_id,),
        ).fetchone()[0] == 1


@pytest.mark.parametrize(
    ("fact_type", "detail_input", "name"),
    [
        (
            "procedure",
            ProcedureCandidateInput(display_name="Biopsy"),
            "Biopsy",
        ),
        (
            "recommendation",
            RecommendationCandidateInput(instruction_text="Rest for a week"),
            "Rest for a week",
        ),
        (
            "follow_up",
            FollowUpCandidateInput(action_text="See cardiology"),
            "See cardiology",
        ),
    ],
)
def test_reject_and_unsupported_terminal_reviews_for_new_types(
    tmp_path: Path,
    fact_type: str,
    detail_input: object,
    name: str,
) -> None:
    ids = SequenceIds("source-1", "candidate-1", "source-2", "candidate-2")
    database, sources, lifecycle = make_services(tmp_path, ids)
    rejected_id = _create_pending(
        sources, lifecycle, "person-1", fact_type, detail_input, name
    )
    unsupported_id = _create_pending(
        sources, lifecycle, "person-1", fact_type, detail_input, name
    )

    rejected = lifecycle.reject(rejected_id)
    unsupported = lifecycle.unsupported(unsupported_id)

    assert rejected.status == "rejected"
    assert unsupported.status == "unsupported"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 0
    with pytest.raises(InvalidTransitionError):
        lifecycle.confirm(rejected_id)
    with pytest.raises(InvalidTransitionError):
        lifecycle.confirm(unsupported_id)


def test_no_canonical_rows_without_explicit_confirmation(tmp_path: Path) -> None:
    ids = SequenceIds(
        "source-1",
        "candidate-1",
        "source-2",
        "candidate-2",
        "source-3",
        "candidate-3",
    )
    database, sources, lifecycle = make_services(tmp_path, ids)
    _create_pending(
        sources,
        lifecycle,
        "person-1",
        "procedure",
        ProcedureCandidateInput(display_name="Stent placement"),
        "Stent placement",
    )
    _create_pending(
        sources,
        lifecycle,
        "person-1",
        "recommendation",
        RecommendationCandidateInput(instruction_text="Sleep more"),
        "Sleep more",
    )
    _create_pending(
        sources,
        lifecycle,
        "person-1",
        "follow_up",
        FollowUpCandidateInput(action_text="Return in June"),
        "Return in June",
    )

    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 0
        for table in (
            "canonical_procedure_details",
            "canonical_recommendation_details",
            "canonical_follow_up_details",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM timeline_events"
        ).fetchone()[0] == 0


def _grant(
    database: SQLiteDatabase,
    *,
    actor_id: str,
    person_id: str,
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
                json.dumps(sorted(OWNER_SCOPES_V4)),
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
                json.dumps(sorted(OWNER_SCOPES_V4)),
                f"consent-{actor_id}",
                actor_id,
                TS,
            ),
        )


def _access(database: SQLiteDatabase, actor_id: str) -> ProductCoreAccess:
    service = FamilyAccessService(
        database,
        clock=FixedClock(datetime(2026, 8, 9, 10, tzinfo=UTC)),
        id_factory=SequenceIds("audit-1", "audit-2", "audit-3", "audit-4", "audit-5"),
        policy=PersonAccessPolicy(),
    )
    return ProductCoreAccess(
        runtime=SimpleNamespace(database=database),
        family_runtime=SimpleNamespace(service=service),
        authenticated=SimpleNamespace(
            actor=SimpleNamespace(actor_id=actor_id),
            record=SimpleNamespace(active_person_id=actor_id),
            session_token="token",
        ),
    )


def test_wrong_person_procedure_candidate_is_hidden_and_not_confirmable(
    tmp_path: Path,
) -> None:
    ids = SequenceIds("source-1", "candidate-1")
    database, sources, lifecycle = make_services(tmp_path, ids, "person-1", "person-2")
    _grant(database, actor_id="actor-a", person_id="person-1")
    _grant(database, actor_id="actor-b", person_id="person-2")
    candidate_id = _create_pending(
        sources,
        lifecycle,
        "person-1",
        "procedure",
        ProcedureCandidateInput(display_name="Stent"),
        "Stent",
    )

    # Repo convention: a resource outside the actor's person is hidden as
    # CandidateNotFoundError, never a scope leak (access.py:503).
    gate_b = _access(database, "actor-b")
    with pytest.raises(CandidateNotFoundError):
        gate_b.preflight_candidate_review(candidate_id)
    with pytest.raises(CandidateNotFoundError):
        lifecycle.confirm(
            candidate_id,
            authorize=gate_b.authorize_candidate_review_mutation(
                candidate_id, action="candidate.confirm"
            ),
        )

    assert (
        lifecycle.list_candidates("person-2", fact_type="procedure") == []
    )
    a_rows = lifecycle.list_candidates("person-1", fact_type="procedure")
    assert [candidate.id for candidate in a_rows] == [candidate_id]
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 0
    # Actor A (correct person) passes the same gate.
    assert gate_b is not None
    assert _access(database, "actor-a").preflight_candidate_review(candidate_id) == "person-1"


def _candidate_fingerprint(
    person_id: str,
    source_id: str,
    extraction_id: str,
    fact_type: str,
    suggestion: object,
    locator: dict[str, object],
) -> str:
    """Mirror app/product_core/document_fact_extraction.py:818-841 composition."""
    detail_values = _detail_payload(fact_type, suggestion)  # type: ignore[arg-type]
    identity_values = dict(detail_values)
    if fact_type == "procedure":
        identity_values["normalized_name"] = normalize_fact_name(
            str(detail_values["display_name"])
        )
    elif fact_type == "recommendation":
        identity_values["normalized_instruction"] = normalize_fact_name(
            str(detail_values["instruction_text"])
        )
    elif fact_type == "follow_up":
        identity_values["normalized_action"] = normalize_fact_name(
            str(detail_values["action_text"])
        )
    return _fingerprint(
        [person_id, source_id, extraction_id, fact_type, locator, identity_values]
    )


def test_candidate_fingerprint_is_deterministic_and_text_sensitive() -> None:
    locator: dict[str, object] = {"kind": "document_text_span", "page_number": 2}
    suggestion = ProcedureSuggestion(
        page_number=2,
        evidence_quote="Procedure: colonoscopy completed on 2026-03-01",
        display_name="Colonoscopy",
        date_text="2026-03-01",
    )
    first = _candidate_fingerprint("p1", "s1", "e1", "procedure", suggestion, locator)
    second = _candidate_fingerprint("p1", "s1", "e1", "procedure", suggestion, locator)
    assert first == second

    moved = suggestion.model_copy(update={"date_text": "2026-04-15"})
    assert _candidate_fingerprint("p1", "s1", "e1", "procedure", moved, locator) != first

    follow_up = FollowUpSuggestion(
        page_number=3,
        evidence_quote="Follow up with cardiology in 3 months",
        action_text="See cardiology",
        timing_text="in 3 months",
    )
    base = _candidate_fingerprint("p1", "s1", "e1", "follow_up", follow_up, locator)
    retimed = follow_up.model_copy(update={"timing_text": "in 6 months"})
    assert (
        _candidate_fingerprint("p1", "s1", "e1", "follow_up", retimed, locator) != base
    )
