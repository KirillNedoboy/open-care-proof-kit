from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.product_core.models import ensure_utc_datetime, isoformat_utc


@dataclass(frozen=True)
class Migration:
    version: int
    statements: tuple[str, ...]


PRODUCT_MIGRATIONS = (
    Migration(
        version=1,
        statements=(
            """
            CREATE TABLE sources (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                source_type TEXT NOT NULL CHECK (source_type IN ('manual_entry', 'plain_text')),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                UNIQUE (person_id, source_type, content_hash)
            )
            """,
            """
            CREATE TABLE candidate_facts (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                source_id TEXT NOT NULL REFERENCES sources(id),
                fact_type TEXT NOT NULL CHECK (fact_type = 'medication'),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'corrected', 'rejected')
                ),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                predecessor_candidate_id TEXT REFERENCES candidate_facts(id),
                CHECK (
                    predecessor_candidate_id IS NULL OR predecessor_candidate_id <> id
                ),
                CHECK (
                    (status = 'pending' AND reviewed_at IS NULL)
                    OR (status <> 'pending' AND reviewed_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE canonical_medication_records (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                candidate_id TEXT NOT NULL UNIQUE REFERENCES candidate_facts(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                confirmed_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            CREATE TABLE timeline_events (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL CHECK (length(trim(person_id)) > 0),
                canonical_record_id TEXT NOT NULL REFERENCES canonical_medication_records(id),
                source_id TEXT NOT NULL REFERENCES sources(id),
                event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
                event_at TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                UNIQUE (canonical_record_id, event_type)
            )
            """,
            "CREATE INDEX candidate_facts_person_status_idx ON candidate_facts(person_id, status)",
            (
                "CREATE INDEX canonical_medication_records_person_active_idx "
                "ON canonical_medication_records(person_id, is_active)"
            ),
            (
                "CREATE INDEX timeline_events_person_event_at_idx "
                "ON timeline_events(person_id, event_at, id)"
            ),
        ),
    ),
    Migration(
        version=2,
        statements=(
            "PRAGMA defer_foreign_keys=ON",
            """
            CREATE TABLE people (
                person_id TEXT PRIMARY KEY CHECK (length(trim(person_id)) > 0),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                date_of_birth TEXT CHECK (
                    date_of_birth IS NULL OR (
                        length(date_of_birth) = 10 AND date(date_of_birth) = date_of_birth
                    )
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            INSERT INTO people (
                person_id, display_name, date_of_birth, created_at, updated_at, is_active
            )
            SELECT person_id, 'Imported profile', NULL, ?, ?, 1
            FROM (
                SELECT person_id FROM sources
                UNION SELECT person_id FROM candidate_facts
                UNION SELECT person_id FROM canonical_medication_records
                UNION SELECT person_id FROM timeline_events
            )
            """,
            """
            CREATE TABLE sources_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_type TEXT NOT NULL CHECK (source_type IN ('manual_entry', 'plain_text')),
                relative_path TEXT NOT NULL CHECK (length(trim(relative_path)) > 0),
                content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                UNIQUE (person_id, source_type, content_hash)
            )
            """,
            """
            CREATE TABLE candidate_facts_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                fact_type TEXT NOT NULL CHECK (fact_type = 'medication'),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'corrected', 'rejected')
                ),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                predecessor_candidate_id TEXT REFERENCES candidate_facts_phase_1d(id),
                CHECK (predecessor_candidate_id IS NULL OR predecessor_candidate_id <> id),
                CHECK (
                    (status = 'pending' AND reviewed_at IS NULL)
                    OR (status <> 'pending' AND reviewed_at IS NOT NULL)
                )
            )
            """,
            """
            CREATE TABLE canonical_medication_records_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                candidate_id TEXT NOT NULL UNIQUE REFERENCES candidate_facts_phase_1d(id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
                normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
                schedule_text TEXT,
                note TEXT,
                confirmed_at TEXT NOT NULL,
                is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
            )
            """,
            """
            CREATE TABLE timeline_events_phase_1d (
                id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES people(person_id),
                canonical_record_id TEXT NOT NULL
                    REFERENCES canonical_medication_records_phase_1d(id),
                source_id TEXT NOT NULL REFERENCES sources_phase_1d(id),
                event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
                event_at TEXT NOT NULL,
                title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                UNIQUE (canonical_record_id, event_type)
            )
            """,
            "INSERT INTO sources_phase_1d SELECT * FROM sources",
            "INSERT INTO candidate_facts_phase_1d SELECT * FROM candidate_facts",
            (
                "INSERT INTO canonical_medication_records_phase_1d "
                "SELECT * FROM canonical_medication_records"
            ),
            "INSERT INTO timeline_events_phase_1d SELECT * FROM timeline_events",
            "DROP TABLE timeline_events",
            "DROP TABLE canonical_medication_records",
            "DROP TABLE candidate_facts",
            "DROP TABLE sources",
            "ALTER TABLE sources_phase_1d RENAME TO sources",
            "ALTER TABLE candidate_facts_phase_1d RENAME TO candidate_facts",
            (
                "ALTER TABLE canonical_medication_records_phase_1d "
                "RENAME TO canonical_medication_records"
            ),
            "ALTER TABLE timeline_events_phase_1d RENAME TO timeline_events",
            (
                "CREATE INDEX people_active_display_name_idx ON people("
                "is_active, display_name COLLATE NOCASE, person_id)"
            ),
            "CREATE INDEX candidate_facts_person_status_idx ON candidate_facts(person_id, status)",
            (
                "CREATE INDEX canonical_medication_records_person_active_idx "
                "ON canonical_medication_records(person_id, is_active)"
            ),
            (
                "CREATE INDEX timeline_events_person_event_at_idx "
                "ON timeline_events(person_id, event_at, id)"
            ),
        ),
    ),
)


class MigrationRunner:
    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        migrations: tuple[Migration, ...] = PRODUCT_MIGRATIONS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.migrations = migrations
        self.clock = clock or (lambda: datetime.now(UTC))
        versions = [migration.version for migration in migrations]
        if versions != sorted(set(versions)):
            raise ValueError("migration versions must be unique and sorted")

    def migrate(self) -> None:
        connection = self.connection_factory()
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            self._bootstrap(connection)
            applied_versions = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            for migration in self.migrations:
                if migration.version in applied_versions:
                    continue
                self._apply_migration(connection, migration)
        finally:
            connection.close()

    @staticmethod
    def _bootstrap(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN")
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _apply_migration(self, connection: sqlite3.Connection, migration: Migration) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            already_applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (migration.version,),
            ).fetchone()
            if already_applied is not None:
                connection.commit()
                return
            applied_at = isoformat_utc(ensure_utc_datetime(self.clock()))
            for statement in migration.statements:
                if migration.version == 2 and statement.lstrip().startswith("INSERT INTO people"):
                    connection.execute(statement, (applied_at, applied_at))
                else:
                    connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (migration.version, applied_at),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
