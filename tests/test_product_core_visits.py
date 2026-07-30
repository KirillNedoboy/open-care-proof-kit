from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.product_core.errors import PersonNotFoundError, VisitNotFoundError
from app.product_core.models import Person
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
        return f"id-{self.value}"


def _service(tmp_path: Path) -> VisitPlanningService:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        for person_id in ("person-1", "person-2"):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=person_id,
                    created_at=now,
                    updated_at=now,
                    is_active=True,
                )
            )
    return VisitPlanningService(database, clock=FixedClock(now), id_factory=SequenceIds())


def test_visit_service_persists_lists_and_updates_a_visit(tmp_path: Path) -> None:
    service = _service(tmp_path)

    visit = service.create_visit(
        "person-1",
        title="  Cardiology follow-up  ",
        specialist="  Cardiologist  ",
        scheduled_date=date(2020, 1, 2),
    )
    updated = service.update_visit(
        visit.visit_id,
        title="Review",
        specialist=None,
        scheduled_date=None,
        update_fields=frozenset({"title", "specialist", "scheduled_date"}),
    )

    assert visit.visit_id == "id-1"
    assert visit.title == "Cardiology follow-up"
    assert visit.specialist == "Cardiologist"
    assert visit.scheduled_date == date(2020, 1, 2)
    assert [item.visit_id for item in service.list_visits("person-1")] == [visit.visit_id]
    assert updated.title == "Review"
    assert updated.specialist is None
    assert updated.scheduled_date is None


def test_visit_service_rejects_unknown_person_and_empty_patch(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(PersonNotFoundError):
        service.create_visit("missing", title="Visit")
    visit = service.create_visit("person-1", title="Visit")
    with pytest.raises(ValueError, match="update field"):
        service.update_visit(visit.visit_id, update_fields=frozenset())
    with pytest.raises(ValueError, match="title"):
        service.update_visit(
            visit.visit_id,
            title=None,
            update_fields=frozenset({"title"}),
        )


def test_question_service_reorders_contiguously_and_isolates_visits(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first_visit = service.create_visit("person-1", title="First")
    second_visit = service.create_visit("person-1", title="Second")
    service.create_question(first_visit.visit_id, "First question")
    second = service.create_question(first_visit.visit_id, "Second question")
    third = service.create_question(first_visit.visit_id, "Third question")
    other = service.create_question(second_visit.visit_id, "Other visit question")

    moved = service.update_question(
        third.question_id,
        position=0,
        update_fields=frozenset({"position"}),
    )
    service.delete_question(second.question_id)

    assert moved.position == 0
    first_visit_questions = [
        (item.question_text, item.position)
        for item in service.list_questions(first_visit.visit_id)
    ]
    assert first_visit_questions == [
        ("Third question", 0),
        ("First question", 1),
    ]
    second_visit_questions = [
        (item.question_text, item.position)
        for item in service.list_questions(second_visit.visit_id)
    ]
    assert second_visit_questions == [
        ("Other visit question", 0)
    ]
    assert other.visit_id == second_visit.visit_id


def test_question_service_rejects_invalid_updates_and_unknown_visit(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(VisitNotFoundError):
        service.create_question("missing", "Question")
    visit = service.create_visit("person-1", title="Visit")
    question = service.create_question(visit.visit_id, "Question")
    with pytest.raises(ValueError, match="update field"):
        service.update_question(question.question_id, update_fields=frozenset())
    with pytest.raises(ValueError, match="question_text"):
        service.update_question(
            question.question_id,
            question_text="  ",
            update_fields=frozenset({"question_text"}),
        )
    with pytest.raises(ValueError, match="position"):
        service.update_question(
            question.question_id,
            position=-1,
            update_fields=frozenset({"position"}),
        )


def test_question_service_updates_text_without_changing_position(tmp_path: Path) -> None:
    service = _service(tmp_path)
    visit = service.create_visit("person-1", title="Visit")
    question = service.create_question(visit.visit_id, "Original")

    updated = service.update_question(
        question.question_id,
        question_text="  Revised question  ",
        update_fields=frozenset({"question_text"}),
    )

    assert updated.question_text == "Revised question"
    assert updated.position == 0
    assert service.list_questions(visit.visit_id) == [updated]
