from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.errors import (
    VisitBriefAlreadyExistsError,
    VisitBriefConflictError,
    VisitBriefIntegrityError,
)
from app.product_core.models import Person
from app.product_core.persisted_visit_briefs import PersistedVisitBriefService
from app.product_core.services import MedicationLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visits import VisitPlanningService


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
        return f"brief-id-{self.value}"


def _services(tmp_path: Path) -> tuple[PersistedVisitBriefService, VisitPlanningService]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 7, 30, 12, tzinfo=UTC))
    ids = SequenceIds()
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=clock(),
                updated_at=clock(),
                is_active=True,
            )
        )
    return (
        PersistedVisitBriefService(database, clock=clock, id_factory=ids),
        VisitPlanningService(database, clock=clock, id_factory=ids),
    )


def test_initialize_creates_one_visit_brief_and_a_metadata_only_audit_event(
    tmp_path: Path,
) -> None:
    briefs, visits = _services(tmp_path)
    visit = visits.create_visit("person-1", title="Cardiology review")

    brief = briefs.initialize(visit.visit_id)

    assert brief.visit_id == visit.visit_id
    assert brief.current_revision_number is None
    assert briefs.get(visit.visit_id) == brief
    with pytest.raises(VisitBriefAlreadyExistsError):
        briefs.initialize(visit.visit_id)


def test_generation_edit_and_restore_append_immutable_revisions(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 7, 30, 12, tzinfo=UTC))
    ids = SequenceIds()
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=clock(),
                updated_at=clock(),
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(database, clock=clock, id_factory=ids)
    visits = VisitPlanningService(database, clock=clock, id_factory=ids)
    briefs = PersistedVisitBriefService(
        database, clock=clock, id_factory=ids, source_reader=sources.store.read
    )
    source = sources.register_manual_entry("person-1", "Aspirin", note="Recorded note")
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Aspirin",
        schedule_text="morning",
        note="Recorded note",
    )
    record = lifecycle.confirm(candidate.id)
    visit = visits.create_visit("person-1", title="Cardiology review")
    visits.create_question(visit.visit_id, "What should I ask?")
    briefs.initialize(visit.visit_id)

    first = briefs.generate(
        visit.visit_id, selected_record_ids=[record.id], expected_current_revision_number=None
    )
    edited = briefs.save_user_edit(
        visit.visit_id, preparation_notes="Bring records.", expected_current_revision_number=1
    )
    restored = briefs.restore(visit.visit_id, revision_number=1, expected_current_revision_number=2)

    assert first.revision_number == 1
    assert edited.revision_number == 2
    assert "Bring records." not in first.rendered_markdown
    assert "Bring records." in edited.rendered_markdown
    assert restored.current_revision_number == 1
    assert len(briefs.list_revisions(visit.visit_id)) == 2
    assert briefs.staleness(visit.visit_id, first.revision_number).state == "current"
    with pytest.raises(VisitBriefConflictError):
        briefs.save_user_edit(
            visit.visit_id,
            preparation_notes="outdated",
            expected_current_revision_number=2,
        )
    with database.uow() as uow:
        audit_events = uow.visit_brief_audit.list_for_brief(restored.brief_id)
        assert any(
            event.action == "concurrency_conflict" and event.outcome == "rejected"
            for event in audit_events
        )
        uow.connection.execute(
            (
                "UPDATE visit_brief_revisions SET rendered_markdown = 'corrupted' "
                "WHERE revision_id = ?"
            ),
            (first.revision_id,),
        )
    with pytest.raises(VisitBriefIntegrityError):
        briefs.get_revision(visit.visit_id, first.revision_number)
