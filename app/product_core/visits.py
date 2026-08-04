from __future__ import annotations

import unicodedata
from datetime import date

from app.product_core.errors import (
    PersonNotFoundError,
    VisitNotFoundError,
    VisitQuestionNotFoundError,
    VisitValidationError,
)
from app.product_core.models import Visit, VisitQuestion, ensure_utc_datetime
from app.product_core.services import (
    Clock,
    IdFactory,
    MutationAuthorizer,
    default_clock,
    default_id_factory,
)
from app.product_core.sqlite import SQLiteDatabase


class VisitPlanningService:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory

    def create_visit(
        self,
        person_id: str,
        *,
        title: str,
        specialist: str | None = None,
        scheduled_date: date | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> Visit:
        now = ensure_utc_datetime(self.clock())
        visit = Visit(
            visit_id=self.id_factory(),
            person_id=person_id,
            title=_required_text(title, "title"),
            specialist=_optional_text(specialist, "specialist"),
            scheduled_date=_scheduled_date(scheduled_date),
            created_at=now,
            updated_at=now,
        )
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            uow.visits.insert(visit)
        return visit

    def get_visit(self, visit_id: str) -> Visit:
        with self.database.uow() as uow:
            visit = uow.visits.get(visit_id)
        if visit is None:
            raise VisitNotFoundError(f"visit not found: {visit_id}")
        return visit

    def list_visits(self, person_id: str) -> list[Visit]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.visits.list_for_person(person_id)

    def update_visit(
        self,
        visit_id: str,
        *,
        title: str | None = None,
        specialist: str | None = None,
        scheduled_date: date | None = None,
        update_fields: frozenset[str],
        authorize: MutationAuthorizer | None = None,
    ) -> Visit:
        _validate_update_fields(update_fields, {"title", "specialist", "scheduled_date"})
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            existing = uow.visits.get(visit_id)
            if existing is None:
                raise VisitNotFoundError(f"visit not found: {visit_id}")
            visit = Visit(
                visit_id=existing.visit_id,
                person_id=existing.person_id,
                title=(
                    existing.title
                    if "title" not in update_fields
                    else _required_text(title, "title")
                ),
                specialist=(
                    existing.specialist
                    if "specialist" not in update_fields
                    else _optional_text(specialist, "specialist")
                ),
                scheduled_date=(
                    existing.scheduled_date
                    if "scheduled_date" not in update_fields
                    else _scheduled_date(scheduled_date)
                ),
                created_at=existing.created_at,
                updated_at=now,
            )
            uow.visits.update(visit)
        return visit

    def create_question(
        self,
        visit_id: str,
        question_text: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> VisitQuestion:
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            if uow.visits.get(visit_id) is None:
                raise VisitNotFoundError(f"visit not found: {visit_id}")
            question = VisitQuestion(
                question_id=self.id_factory(),
                visit_id=visit_id,
                question_text=_required_text(question_text, "question_text"),
                position=len(uow.visit_questions.list_for_visit(visit_id)),
                created_at=now,
                updated_at=now,
            )
            uow.visit_questions.insert(question)
        return question

    def list_questions(self, visit_id: str) -> list[VisitQuestion]:
        with self.database.uow() as uow:
            if uow.visits.get(visit_id) is None:
                raise VisitNotFoundError(f"visit not found: {visit_id}")
            return uow.visit_questions.list_for_visit(visit_id)

    def update_question(
        self,
        question_id: str,
        *,
        question_text: str | None = None,
        position: int | None = None,
        update_fields: frozenset[str],
        authorize: MutationAuthorizer | None = None,
    ) -> VisitQuestion:
        _validate_update_fields(update_fields, {"question_text", "position"})
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            existing = uow.visit_questions.get(question_id)
            if existing is None:
                raise VisitQuestionNotFoundError(f"visit question not found: {question_id}")
            questions = uow.visit_questions.list_for_visit(existing.visit_id)
            next_position = existing.position
            if "position" in update_fields:
                if position is None or position < 0 or position >= len(questions):
                    raise VisitValidationError("position must reference a question in the visit")
                next_position = position
            question = VisitQuestion(
                question_id=existing.question_id,
                visit_id=existing.visit_id,
                question_text=(
                    existing.question_text
                    if "question_text" not in update_fields
                    else _required_text(question_text, "question_text")
                ),
                position=next_position,
                created_at=existing.created_at,
                updated_at=now,
            )
            if next_position != existing.position:
                reordered = [item for item in questions if item.question_id != question_id]
                reordered.insert(next_position, question)
                uow.visit_questions.replace_positions(
                    existing.visit_id,
                    {item.question_id: index for index, item in enumerate(reordered)},
                    now,
                )
            else:
                uow.visit_questions.update(question)
        return question

    def delete_question(
        self,
        question_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> None:
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            existing = uow.visit_questions.get(question_id)
            if existing is None:
                raise VisitQuestionNotFoundError(f"visit question not found: {question_id}")
            uow.visit_questions.delete(question_id)
            remaining = uow.visit_questions.list_for_visit(existing.visit_id)
            uow.visit_questions.replace_positions(
                existing.visit_id,
                {item.question_id: index for index, item in enumerate(remaining)},
                now,
            )


def _required_text(value: str | None, field_name: str) -> str:
    if value is None:
        raise VisitValidationError(f"{field_name} must not be null")
    if not isinstance(value, str):
        raise VisitValidationError(f"{field_name} must be text")
    _reject_control_characters(value, field_name)
    cleaned = value.strip()
    if not cleaned:
        raise VisitValidationError(f"{field_name} must not be blank")
    return cleaned


def _optional_text(value: str | None, field_name: str) -> str | None:
    return None if value is None else _required_text(value, field_name)


def _scheduled_date(value: date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    raise VisitValidationError("scheduled_date must be an ISO calendar date")


def _reject_control_characters(value: str, field_name: str) -> None:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise VisitValidationError(f"{field_name} must not contain control characters")


def _validate_update_fields(update_fields: frozenset[str], allowed: set[str]) -> None:
    if not update_fields:
        raise VisitValidationError("an update field is required")
    if not update_fields.issubset(allowed):
        raise VisitValidationError("unsupported update field")
