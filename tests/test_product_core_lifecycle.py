import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.errors import (
    IntegrityStorageError,
    InvalidTransitionError,
)
from app.product_core.models import Person
from app.product_core.services import MedicationLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase


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
) -> tuple[SQLiteDatabase, SourceService, MedicationLifecycleService]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1", "person-2")
    clock = FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC))
    source_service = SourceService(
        database,
        tmp_path / "sources",
        clock=clock,
        id_factory=ids,
    )
    lifecycle = MedicationLifecycleService(database, clock=clock, id_factory=ids)
    return database, source_service, lifecycle


def seed_people(database: SQLiteDatabase, *person_ids: str) -> None:
    now = datetime(2026, 7, 26, 10, tzinfo=UTC)
    with database.uow() as uow:
        for person_id in person_ids:
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=f"Profile {person_id}",
                    created_at=now,
                    updated_at=now,
                    is_active=True,
                )
            )


def create_pending(
    tmp_path: Path,
    ids: SequenceIds,
) -> tuple[SQLiteDatabase, SourceService, MedicationLifecycleService, str]:
    database, sources, lifecycle = make_services(tmp_path, ids)
    source = sources.register_manual_entry("person-1", "Aspirin")
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="  Aspirin  ",
        schedule_text=None,
        note=None,
    )
    return database, sources, lifecycle, candidate.id


def test_candidate_preserves_display_name_and_normalizes_for_comparison(tmp_path: Path) -> None:
    _, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1"),
    )

    candidate = lifecycle.get_candidate(candidate_id)

    assert candidate.display_name == "Aspirin"
    assert candidate.normalized_name == "aspirin"
    assert candidate.status == "pending"
    assert candidate.reviewed_at is None


def test_confirmation_atomically_creates_canonical_and_timeline_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1", "canonical-1", "event-1"),
    )

    first = lifecycle.confirm(candidate_id)
    second = lifecycle.confirm(candidate_id)

    assert first.id == second.id
    assert first.is_active is True
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_medication_records"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM timeline_events").fetchone()[0] == 1
        assert connection.execute(
            "SELECT status, reviewed_at FROM candidate_facts WHERE id = ?",
            (candidate_id,),
        ).fetchone()[0] == "confirmed"


def test_confirmed_candidate_without_canonical_is_an_integrity_error(tmp_path: Path) -> None:
    database, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1"),
    )
    with database.connect() as connection:
        connection.execute(
            "UPDATE candidate_facts SET status='confirmed', reviewed_at=? WHERE id=?",
            ("2026-07-26T10:00:00+00:00", candidate_id),
        )

    with pytest.raises(IntegrityStorageError):
        lifecycle.confirm(candidate_id)


@pytest.mark.parametrize("operation", ["confirm", "reject"])
def test_corrected_and_rejected_candidates_cannot_be_confirmed_or_rejected(
    tmp_path: Path,
    operation: str,
) -> None:
    database, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1", "replacement-1"),
    )
    if operation == "confirm":
        lifecycle.reject(candidate_id)
        with pytest.raises(InvalidTransitionError):
            lifecycle.confirm(candidate_id)
    else:
        lifecycle.correct(candidate_id, display_name="Replacement")
        with pytest.raises(InvalidTransitionError):
            lifecycle.reject(candidate_id)
    assert database is not None


def test_correction_marks_original_and_links_replacement_atomically(tmp_path: Path) -> None:
    database, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1", "replacement-1"),
    )

    replacement = lifecycle.correct(candidate_id, display_name="Ibuprofen")

    original = lifecycle.get_candidate(candidate_id)
    assert original.status == "corrected"
    assert original.reviewed_at is not None
    assert replacement.status == "pending"
    assert replacement.predecessor_candidate_id == candidate_id

    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_facts WHERE predecessor_candidate_id = ?",
            (candidate_id,),
        ).fetchone()[0] == 1


def test_failed_correction_leaves_original_pending(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1")
    clock = FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC))
    ids = SequenceIds("source-1", "candidate-1", "candidate-2", "candidate-2")
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(database, clock=clock, id_factory=ids)
    source = sources.register_manual_entry("person-1", "Aspirin")
    first = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Aspirin",
        schedule_text=None,
        note=None,
    )
    second = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Ibuprofen",
        schedule_text=None,
        note=None,
    )

    with pytest.raises(sqlite3.IntegrityError):
        lifecycle.correct(first.id, display_name="Replacement")

    assert lifecycle.get_candidate(first.id).status == "pending"
    assert lifecycle.get_candidate(first.id).reviewed_at is None
    assert lifecycle.get_candidate(second.id).status == "pending"


def test_confirmation_rolls_back_when_timeline_insert_fails(tmp_path: Path) -> None:
    database, _, lifecycle, candidate_id = create_pending(
        tmp_path,
        SequenceIds("source-1", "candidate-1", "canonical-1", "event-1"),
    )
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_timeline_insert
            BEFORE INSERT ON timeline_events
            BEGIN
                SELECT RAISE(ABORT, 'forced timeline failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        lifecycle.confirm(candidate_id)

    assert lifecycle.get_candidate(candidate_id).status == "pending"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_medication_records"
        ).fetchone()[0] == 0


def test_person_isolation_and_deterministic_canonical_ordering(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1", "person-2")
    clock = FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC))
    ids = SequenceIds(
        "source-1",
        "candidate-1",
        "source-2",
        "candidate-2",
        "source-3",
        "candidate-3",
        "canonical-1",
        "event-1",
        "canonical-2",
        "event-2",
        "canonical-3",
        "event-3",
    )
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(database, clock=clock, id_factory=ids)

    candidates = []
    for person_id, name in [("person-1", "Zeta"), ("person-1", "Alpha"), ("person-2", "Other")]:
        source = sources.register_manual_entry(person_id, name)
        candidates.append(
            lifecycle.create_candidate(
                person_id=person_id,
                source_id=source.id,
                display_name=name,
                schedule_text=None,
                note=None,
            )
        )
    canonical = [lifecycle.confirm(candidate.id) for candidate in candidates]

    assert [item.display_name for item in lifecycle.list_active("person-1")] == ["Zeta", "Alpha"]
    assert all(item.person_id == "person-1" for item in lifecycle.list_active("person-1"))
    assert canonical[0].source_id != canonical[1].source_id
