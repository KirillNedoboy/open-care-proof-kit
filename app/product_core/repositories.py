from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Protocol

from app.product_core.models import (
    CandidateFact,
    CandidateStatus,
    CanonicalMedicationRecord,
    Person,
    Source,
    SourceType,
    TimelineEvent,
    Visit,
    VisitQuestion,
    parse_utc_datetime,
)


class PersonRepository(Protocol):
    def get(self, person_id: str) -> Person | None: ...

    def list_active(self) -> list[Person]: ...

    def insert(self, person: Person) -> None: ...

    def update(self, person: Person) -> None: ...


class SourceRepository(Protocol):
    def get(self, source_id: str) -> Source | None: ...

    def find_by_deduplication(
        self,
        person_id: str,
        source_type: SourceType,
        content_hash: str,
    ) -> Source | None: ...

    def insert(self, source: Source) -> None: ...

    def path_referenced(self, relative_path: str) -> bool: ...


class SQLitePersonRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, person_id: str) -> Person | None:
        row = self.connection.execute(
            "SELECT * FROM people WHERE person_id = ?", (person_id,)
        ).fetchone()
        return None if row is None else _person_from_row(row)

    def list_active(self) -> list[Person]:
        rows = self.connection.execute(
            """
            SELECT * FROM people WHERE is_active = 1
            ORDER BY display_name COLLATE NOCASE ASC, person_id ASC
            """
        ).fetchall()
        return [_person_from_row(row) for row in rows]

    def insert(self, person: Person) -> None:
        self.connection.execute(
            """
            INSERT INTO people (
                person_id, display_name, date_of_birth, created_at, updated_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                person.person_id,
                person.display_name,
                None if person.date_of_birth is None else person.date_of_birth.isoformat(),
                person.created_at.isoformat(),
                person.updated_at.isoformat(),
                int(person.is_active),
            ),
        )

    def update(self, person: Person) -> None:
        self.connection.execute(
            """
            UPDATE people SET display_name = ?, date_of_birth = ?, updated_at = ?
            WHERE person_id = ?
            """,
            (
                person.display_name,
                None if person.date_of_birth is None else person.date_of_birth.isoformat(),
                person.updated_at.isoformat(),
                person.person_id,
            ),
        )


class CandidateRepository(Protocol):
    def get(self, candidate_id: str) -> CandidateFact | None: ...

    def list_for_person(
        self,
        person_id: str,
        status: CandidateStatus | None = None,
    ) -> list[CandidateFact]: ...

    def insert(self, candidate: CandidateFact) -> None: ...

    def update_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
        reviewed_at: datetime,
    ) -> None: ...


class CanonicalRepository(Protocol):
    def get(self, record_id: str) -> CanonicalMedicationRecord | None: ...

    def get_by_candidate(self, candidate_id: str) -> CanonicalMedicationRecord | None: ...

    def insert(self, record: CanonicalMedicationRecord) -> None: ...

    def list_active_for_person(self, person_id: str) -> list[CanonicalMedicationRecord]: ...

    def list_for_person(
        self,
        person_id: str,
        include_inactive: bool = False,
    ) -> list[CanonicalMedicationRecord]: ...


class TimelineRepository(Protocol):
    def insert(self, event: TimelineEvent) -> None: ...

    def list_for_person(self, person_id: str) -> list[TimelineEvent]: ...


class VisitRepository(Protocol):
    def get(self, visit_id: str) -> Visit | None: ...

    def list_for_person(self, person_id: str) -> list[Visit]: ...

    def insert(self, visit: Visit) -> None: ...

    def update(self, visit: Visit) -> None: ...


class VisitQuestionRepository(Protocol):
    def get(self, question_id: str) -> VisitQuestion | None: ...

    def list_for_visit(self, visit_id: str) -> list[VisitQuestion]: ...

    def insert(self, question: VisitQuestion) -> None: ...

    def update(self, question: VisitQuestion) -> None: ...

    def delete(self, question_id: str) -> None: ...

    def replace_positions(
        self,
        visit_id: str,
        positions: dict[str, int],
        updated_at: datetime,
    ) -> None: ...


class SQLiteSourceRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, source_id: str) -> Source | None:
        row = self.connection.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        return None if row is None else _source_from_row(row)

    def find_by_deduplication(
        self,
        person_id: str,
        source_type: SourceType,
        content_hash: str,
    ) -> Source | None:
        row = self.connection.execute(
            """
            SELECT * FROM sources
            WHERE person_id = ? AND source_type = ? AND content_hash = ?
            """,
            (person_id, source_type, content_hash),
        ).fetchone()
        return None if row is None else _source_from_row(row)

    def insert(self, source: Source) -> None:
        self.connection.execute(
            """
            INSERT INTO sources (
                id, person_id, source_type, relative_path, content_hash,
                size_bytes, media_type, created_at, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.id,
                source.person_id,
                source.source_type,
                source.relative_path,
                source.content_hash,
                source.size_bytes,
                source.media_type,
                source.created_at.isoformat(),
                json.dumps(source.provenance, ensure_ascii=False, sort_keys=True),
            ),
        )

    def path_referenced(self, relative_path: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM sources WHERE relative_path = ? LIMIT 1",
                (relative_path,),
            ).fetchone()
            is not None
        )


class SQLiteCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, candidate_id: str) -> CandidateFact | None:
        row = self.connection.execute(
            "SELECT * FROM candidate_facts WHERE id = ?", (candidate_id,)
        ).fetchone()
        return None if row is None else _candidate_from_row(row)

    def list_for_person(
        self,
        person_id: str,
        status: CandidateStatus | None = None,
    ) -> list[CandidateFact]:
        query = "SELECT * FROM candidate_facts WHERE person_id = ?"
        parameters: tuple[str, ...] = (person_id,)
        if status is not None:
            query += " AND status = ?"
            parameters += (status,)
        query += " ORDER BY created_at DESC, id ASC"
        rows = self.connection.execute(query, parameters).fetchall()
        return [_candidate_from_row(row) for row in rows]

    def insert(self, candidate: CandidateFact) -> None:
        self.connection.execute(
            """
            INSERT INTO candidate_facts (
                id, person_id, source_id, fact_type, status, display_name,
                normalized_name, schedule_text, note, created_at, reviewed_at,
                predecessor_candidate_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.id,
                candidate.person_id,
                candidate.source_id,
                candidate.fact_type,
                candidate.status,
                candidate.display_name,
                candidate.normalized_name,
                candidate.schedule_text,
                candidate.note,
                candidate.created_at.isoformat(),
                None if candidate.reviewed_at is None else candidate.reviewed_at.isoformat(),
                candidate.predecessor_candidate_id,
            ),
        )

    def update_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
        reviewed_at: datetime,
    ) -> None:
        self.connection.execute(
            """
            UPDATE candidate_facts
            SET status = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (status, reviewed_at.isoformat(), candidate_id),
        )


class SQLiteCanonicalRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, record_id: str) -> CanonicalMedicationRecord | None:
        row = self.connection.execute(
            "SELECT * FROM canonical_medication_records WHERE id = ?", (record_id,)
        ).fetchone()
        return None if row is None else _canonical_from_row(row)

    def get_by_candidate(self, candidate_id: str) -> CanonicalMedicationRecord | None:
        row = self.connection.execute(
            "SELECT * FROM canonical_medication_records WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        return None if row is None else _canonical_from_row(row)

    def insert(self, record: CanonicalMedicationRecord) -> None:
        self.connection.execute(
            """
            INSERT INTO canonical_medication_records (
                id, person_id, candidate_id, source_id, display_name,
                normalized_name, schedule_text, note, confirmed_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.person_id,
                record.candidate_id,
                record.source_id,
                record.display_name,
                record.normalized_name,
                record.schedule_text,
                record.note,
                record.confirmed_at.isoformat(),
                int(record.is_active),
            ),
        )

    def list_active_for_person(self, person_id: str) -> list[CanonicalMedicationRecord]:
        return self.list_for_person(person_id)

    def list_for_person(
        self,
        person_id: str,
        include_inactive: bool = False,
    ) -> list[CanonicalMedicationRecord]:
        query = "SELECT * FROM canonical_medication_records WHERE person_id = ?"
        parameters: tuple[str, ...] = (person_id,)
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY confirmed_at ASC, id ASC"
        rows = self.connection.execute(
            query,
            parameters,
        ).fetchall()
        return [_canonical_from_row(row) for row in rows]


class SQLiteTimelineRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def insert(self, event: TimelineEvent) -> None:
        self.connection.execute(
            """
            INSERT INTO timeline_events (
                id, person_id, canonical_record_id, source_id,
                event_type, event_at, title
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.person_id,
                event.canonical_record_id,
                event.source_id,
                event.event_type,
                event.event_at.isoformat(),
                event.title,
            ),
        )

    def list_for_person(self, person_id: str) -> list[TimelineEvent]:
        rows = self.connection.execute(
            """
            SELECT * FROM timeline_events
            WHERE person_id = ?
            ORDER BY event_at ASC, id ASC
            """,
            (person_id,),
        ).fetchall()
        return [_timeline_from_row(row) for row in rows]


class SQLiteVisitRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, visit_id: str) -> Visit | None:
        row = self.connection.execute(
            "SELECT * FROM visits WHERE visit_id = ?", (visit_id,)
        ).fetchone()
        return None if row is None else _visit_from_row(row)

    def list_for_person(self, person_id: str) -> list[Visit]:
        rows = self.connection.execute(
            """
            SELECT * FROM visits WHERE person_id = ?
            ORDER BY created_at DESC, visit_id ASC
            """,
            (person_id,),
        ).fetchall()
        return [_visit_from_row(row) for row in rows]

    def insert(self, visit: Visit) -> None:
        self.connection.execute(
            """
            INSERT INTO visits (
                visit_id, person_id, title, specialist, scheduled_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                visit.visit_id,
                visit.person_id,
                visit.title,
                visit.specialist,
                None if visit.scheduled_date is None else visit.scheduled_date.isoformat(),
                visit.created_at.isoformat(),
                visit.updated_at.isoformat(),
            ),
        )

    def update(self, visit: Visit) -> None:
        self.connection.execute(
            """
            UPDATE visits
            SET title = ?, specialist = ?, scheduled_date = ?, updated_at = ?
            WHERE visit_id = ?
            """,
            (
                visit.title,
                visit.specialist,
                None if visit.scheduled_date is None else visit.scheduled_date.isoformat(),
                visit.updated_at.isoformat(),
                visit.visit_id,
            ),
        )


class SQLiteVisitQuestionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, question_id: str) -> VisitQuestion | None:
        row = self.connection.execute(
            "SELECT * FROM visit_questions WHERE question_id = ?", (question_id,)
        ).fetchone()
        return None if row is None else _visit_question_from_row(row)

    def list_for_visit(self, visit_id: str) -> list[VisitQuestion]:
        rows = self.connection.execute(
            """
            SELECT * FROM visit_questions WHERE visit_id = ?
            ORDER BY position ASC, question_id ASC
            """,
            (visit_id,),
        ).fetchall()
        return [_visit_question_from_row(row) for row in rows]

    def insert(self, question: VisitQuestion) -> None:
        self.connection.execute(
            """
            INSERT INTO visit_questions (
                question_id, visit_id, question_text, position, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                question.question_id,
                question.visit_id,
                question.question_text,
                question.position,
                question.created_at.isoformat(),
                question.updated_at.isoformat(),
            ),
        )

    def update(self, question: VisitQuestion) -> None:
        self.connection.execute(
            """
            UPDATE visit_questions
            SET question_text = ?, position = ?, updated_at = ?
            WHERE question_id = ?
            """,
            (
                question.question_text,
                question.position,
                question.updated_at.isoformat(),
                question.question_id,
            ),
        )

    def delete(self, question_id: str) -> None:
        self.connection.execute("DELETE FROM visit_questions WHERE question_id = ?", (question_id,))

    def replace_positions(
        self,
        visit_id: str,
        positions: dict[str, int],
        updated_at: datetime,
    ) -> None:
        count = len(positions)
        if count == 0:
            return
        self.connection.execute(
            "UPDATE visit_questions SET position = position + ? WHERE visit_id = ?",
            (count, visit_id),
        )
        for question_id, position in positions.items():
            self.connection.execute(
                """
                UPDATE visit_questions SET position = ?, updated_at = ?
                WHERE question_id = ? AND visit_id = ?
                """,
                (position, updated_at.isoformat(), question_id, visit_id),
            )


def _source_from_row(row: sqlite3.Row) -> Source:
    return Source(
        id=row["id"],
        person_id=row["person_id"],
        source_type=row["source_type"],
        relative_path=row["relative_path"],
        content_hash=row["content_hash"],
        size_bytes=row["size_bytes"],
        media_type=row["media_type"],
        created_at=parse_utc_datetime(row["created_at"]),
        provenance=json.loads(row["provenance_json"]),
    )


def _person_from_row(row: sqlite3.Row) -> Person:
    return Person(
        person_id=row["person_id"],
        display_name=row["display_name"],
        date_of_birth=(
            None if row["date_of_birth"] is None else date.fromisoformat(row["date_of_birth"])
        ),
        created_at=parse_utc_datetime(row["created_at"]),
        updated_at=parse_utc_datetime(row["updated_at"]),
        is_active=bool(row["is_active"]),
    )


def _candidate_from_row(row: sqlite3.Row) -> CandidateFact:
    return CandidateFact(
        id=row["id"],
        person_id=row["person_id"],
        source_id=row["source_id"],
        fact_type=row["fact_type"],
        status=row["status"],
        display_name=row["display_name"],
        normalized_name=row["normalized_name"],
        schedule_text=row["schedule_text"],
        note=row["note"],
        created_at=parse_utc_datetime(row["created_at"]),
        reviewed_at=(
            None if row["reviewed_at"] is None else parse_utc_datetime(row["reviewed_at"])
        ),
        predecessor_candidate_id=row["predecessor_candidate_id"],
    )


def _canonical_from_row(row: sqlite3.Row) -> CanonicalMedicationRecord:
    return CanonicalMedicationRecord(
        id=row["id"],
        person_id=row["person_id"],
        candidate_id=row["candidate_id"],
        source_id=row["source_id"],
        display_name=row["display_name"],
        normalized_name=row["normalized_name"],
        schedule_text=row["schedule_text"],
        note=row["note"],
        confirmed_at=parse_utc_datetime(row["confirmed_at"]),
        is_active=bool(row["is_active"]),
    )


def _timeline_from_row(row: sqlite3.Row) -> TimelineEvent:
    return TimelineEvent(
        id=row["id"],
        person_id=row["person_id"],
        canonical_record_id=row["canonical_record_id"],
        source_id=row["source_id"],
        event_type=row["event_type"],
        event_at=parse_utc_datetime(row["event_at"]),
        title=row["title"],
    )


def _visit_from_row(row: sqlite3.Row) -> Visit:
    return Visit(
        visit_id=row["visit_id"],
        person_id=row["person_id"],
        title=row["title"],
        specialist=row["specialist"],
        scheduled_date=(
            None if row["scheduled_date"] is None else date.fromisoformat(row["scheduled_date"])
        ),
        created_at=parse_utc_datetime(row["created_at"]),
        updated_at=parse_utc_datetime(row["updated_at"]),
    )


def _visit_question_from_row(row: sqlite3.Row) -> VisitQuestion:
    return VisitQuestion(
        question_id=row["question_id"],
        visit_id=row["visit_id"],
        question_text=row["question_text"],
        position=row["position"],
        created_at=parse_utc_datetime(row["created_at"]),
        updated_at=parse_utc_datetime(row["updated_at"]),
    )
