from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Protocol

from app.product_core.models import (
    CandidateFact,
    CandidateStatus,
    CanonicalMedicationRecord,
    Source,
    SourceType,
    TimelineEvent,
    parse_utc_datetime,
)


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


class CandidateRepository(Protocol):
    def get(self, candidate_id: str) -> CandidateFact | None: ...

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


class TimelineRepository(Protocol):
    def insert(self, event: TimelineEvent) -> None: ...


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
        rows = self.connection.execute(
            """
            SELECT * FROM canonical_medication_records
            WHERE person_id = ? AND is_active = 1
            ORDER BY confirmed_at ASC, id ASC
            """,
            (person_id,),
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
