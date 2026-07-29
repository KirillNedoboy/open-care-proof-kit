from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.product_core.errors import PersonNotFoundError
from app.product_core.services import PeopleService, SourceService
from app.product_core.sqlite import SQLiteDatabase


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
        return f"person-{self.value}"


def test_people_service_creates_lists_and_updates_profiles(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 7, 29, 12, tzinfo=UTC))
    people = PeopleService(database, clock=clock, id_factory=SequenceIds())

    zeta = people.create("  Zeta  ")
    alpha = people.create("Alpha", date_of_birth=date(2000, 1, 2))
    updated = people.update(
        alpha.person_id,
        display_name="  Ada  ",
        date_of_birth=None,
        update_date_of_birth=True,
    )

    assert zeta.person_id == "person-1"
    assert zeta.created_at == clock()
    assert alpha.date_of_birth == date(2000, 1, 2)
    assert updated.display_name == "Ada"
    assert updated.date_of_birth is None
    assert updated.updated_at == clock()
    assert [person.display_name for person in people.list_active()] == ["Ada", "Zeta"]


def test_people_service_rejects_invalid_or_unknown_people(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    people = PeopleService(
        database,
        clock=FixedClock(datetime(2026, 7, 29, 12, tzinfo=UTC)),
        id_factory=SequenceIds(),
    )

    with pytest.raises(ValueError, match="display_name"):
        people.create(" \t ")
    with pytest.raises(ValueError, match="date_of_birth"):
        people.create("Ada", date_of_birth=date(2026, 7, 30))
    with pytest.raises(PersonNotFoundError):
        people.get("missing")
    with pytest.raises(PersonNotFoundError):
        people.update("missing", display_name="Ada")


def test_source_registration_rejects_unknown_person_after_migration(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    sources = SourceService(database, tmp_path / "sources")

    with pytest.raises(PersonNotFoundError):
        sources.register_manual_entry("missing", "Aspirin")
