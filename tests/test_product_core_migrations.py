import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.product_core.migrations import PRODUCT_MIGRATIONS, Migration, MigrationRunner
from app.product_core.sqlite import SQLiteDatabase


def test_fresh_and_repeated_migrations_bootstrap_schema_and_foreign_keys(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")

    database.migrate()
    database.migrate()

    with database.connect() as connection:
        assert [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ] == [1, 2, 3, 4, 5, 6, 7]
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {
        "schema_migrations",
        "people",
        "sources",
        "candidate_facts",
        "canonical_records",
        "timeline_events",
        "visits",
        "visit_questions",
        "visit_briefs",
        "visit_brief_revisions",
        "visit_brief_evidence_selections",
        "visit_brief_audit_events",
        "agent_disclosure_consents",
        "agent_execution_receipts",
    }.issubset(table_names)


def test_phase_1c_upgrade_backfills_people_and_preserves_records(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:1]).migrate()
    with database.connect() as connection:
        connection.execute("BEGIN")
        connection.execute(
            """INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("source-1", "legacy-one", "manual_entry", "source-1.json", "a" * 64, 1,
             "application/json", "2026-01-01T00:00:00+00:00", "{}"),
        )
        connection.execute(
            """INSERT INTO candidate_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("candidate-1", "legacy-two", "source-1", "medication", "confirmed", "Aspirin",
             "aspirin", None, None, "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", None),
        )
        connection.execute(
            """INSERT INTO canonical_medication_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("record-1", "legacy-three", "candidate-1", "source-1", "Aspirin", "aspirin",
             None, None, "2026-01-02T00:00:00+00:00", 1),
        )
        connection.execute(
            """INSERT INTO timeline_events VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("event-1", "legacy-four", "record-1", "source-1", "medication_confirmed",
             "2026-01-02T00:00:00+00:00", "Medication confirmed: Aspirin"),
        )
        connection.commit()

    database.migrate()

    with database.connect() as connection:
        people = [
            tuple(row)
            for row in connection.execute(
                "SELECT person_id, display_name, date_of_birth, is_active "
                "FROM people ORDER BY person_id"
            ).fetchall()
        ]
        assert people == [
            ("legacy-four", "Imported profile", None, 1),
            ("legacy-one", "Imported profile", None, 1),
            ("legacy-three", "Imported profile", None, 1),
            ("legacy-two", "Imported profile", None, 1),
        ]
        source_people = [
            tuple(row)
            for row in connection.execute("SELECT person_id FROM sources").fetchall()
        ]
        candidate_people = [
            tuple(row)
            for row in connection.execute("SELECT person_id FROM candidate_facts").fetchall()
        ]
        assert source_people == [("legacy-one",)]
        assert candidate_people == [("legacy-two",)]
        assert [tuple(row) for row in connection.execute(
            "SELECT person_id FROM canonical_records"
        ).fetchall()] == [("legacy-three",)]
        assert [tuple(row) for row in connection.execute(
            "SELECT person_id FROM timeline_events"
        ).fetchall()] == [("legacy-four",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("bad", "unknown", "manual_entry", "bad.json", "b" * 64, 1,
                 "application/json", "2026-01-01T00:00:00+00:00", "{}"),
            )


def test_phase_1e_a_upgrade_from_version_two_preserves_existing_records(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:2]).migrate()
    with database.connect() as connection:
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO people (
                person_id, display_name, date_of_birth, created_at, updated_at, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("person-1", "Ada", None, "2026-07-30T00:00:00+00:00", "2026-07-30T00:00:00+00:00", 1),
        )
        connection.execute(
            """
            INSERT INTO sources (
                id, person_id, source_type, relative_path, content_hash,
                size_bytes, media_type, created_at, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("source-1", "person-1", "manual_entry", "source-1.json", "b" * 64, 1,
             "application/json", "2026-07-30T00:00:00+00:00", "{}"),
        )
        connection.commit()

    database.migrate()

    with database.connect() as connection:
        assert [row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()] == [1, 2, 3, 4, 5, 6, 7]
        person_name = connection.execute(
            "SELECT display_name FROM people WHERE person_id = 'person-1'"
        ).fetchone()[0]
        source_id = connection.execute(
            "SELECT id FROM sources WHERE id = 'source-1'"
        ).fetchone()[0]
        assert person_name == "Ada"
        assert source_id == "source-1"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO visits (
                    visit_id, person_id, title, specialist, scheduled_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("visit-missing", "missing", "Visit", None, None,
                "2026-07-30T00:00:00+00:00", "2026-07-30T00:00:00+00:00"),
            )


def test_phase_1e_b_upgrade_from_version_three_preserves_visits(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:3]).migrate()
    timestamp = "2026-07-30T00:00:00+00:00"
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("person-1", "Ada", None, timestamp, timestamp, 1),
        )
        connection.execute(
            "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("visit-1", "person-1", "Review", None, None, timestamp, timestamp),
        )

    database.migrate()

    with database.connect() as connection:
        title = connection.execute(
            "SELECT title FROM visits WHERE visit_id = 'visit-1'"
        ).fetchone()[0]
        assert title == "Review"
        assert connection.execute("SELECT COUNT(*) FROM visit_briefs").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO visit_briefs VALUES (?, ?, ?, ?, ?)",
                ("brief-bad", "unknown-visit", None, timestamp, timestamp),
            )


def test_failed_migration_is_rolled_back_and_not_recorded(tmp_path: Path) -> None:
    database_path = tmp_path / "product.sqlite3"

    def connection_factory() -> sqlite3.Connection:
        return sqlite3.connect(database_path)

    runner = MigrationRunner(
        connection_factory,
        migrations=(
            Migration(
                version=1,
                statements=("CREATE TABLE stable (id INTEGER PRIMARY KEY)",),
            ),
            Migration(
                version=2,
                statements=(
                    "CREATE TABLE rolled_back (id INTEGER PRIMARY KEY)",
                    "THIS IS NOT SQL",
                ),
            ),
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        runner.migrate()

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,)]
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rolled_back'"
        ).fetchone() is None


def test_product_migration_does_not_own_schema_migrations_bootstrap(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")

    database.migrate()

    with database.connect() as connection:
        migration_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='schema_migrations'"
        ).fetchone()[0]
    assert "CREATE TABLE schema_migrations" in migration_sql


def test_concurrent_migrations_are_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "product.sqlite3"
    go_path = tmp_path / "go"
    child_code = """
import sys
import time
from pathlib import Path

from app.product_core.migrations import MigrationRunner
from app.product_core.sqlite import SQLiteDatabase

database = SQLiteDatabase(Path(sys.argv[1]))
runner = MigrationRunner(database.connect)
connection = database.connect()
try:
    runner._bootstrap(connection)
    applied_versions = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    Path(sys.argv[2]).write_text("ready", encoding="utf-8")
    while not Path(sys.argv[3]).exists():
        time.sleep(0.01)
    for migration in runner.migrations:
        if migration.version not in applied_versions:
            runner._apply_migration(connection, migration)
finally:
    connection.close()
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(database_path),
                str(tmp_path / f"ready-{index}"),
                str(go_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(2)
    ]
    deadline = time.monotonic() + 10
    while not all((tmp_path / f"ready-{index}").exists() for index in range(2)):
        assert time.monotonic() < deadline
        assert all(process.poll() is None for process in processes)
        time.sleep(0.01)
    go_path.write_text("go", encoding="utf-8")
    results = [process.communicate(timeout=10) for process in processes]

    assert [process.returncode for process in processes] == [0, 0], results
    database = SQLiteDatabase(database_path)
    connection = database.connect()
    try:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert versions == [1, 2, 3, 4, 5, 6, 7]
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
        ).fetchone() is not None
    finally:
        connection.close()


def test_populated_v6_lifecycle_survives_to_v7_with_behavior_valid(tmp_path: Path) -> None:
    """A populated v6 database (Person, source, candidates, canonical,
    timeline, Visit Brief with medication evidence) survives the v7 cutover
    with identical identity/values and a usable medication lifecycle."""
    import json

    from app.product_core.models import Person
    from app.product_core.services import MedicationLifecycleService, SourceService

    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:6]).migrate()
    timestamp = "2026-07-26T10:00:00+00:00"
    with database.connect() as connection:
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("person-1", "Ada", None, timestamp, timestamp, 1),
        )
        connection.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("src-1", "person-1", "manual_entry", "src-1.json", "a" * 64, 1,
             "application/json", timestamp, json.dumps({"entry_method": "manual"})),
        )
        connection.execute(
            "INSERT INTO candidate_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("cand-1", "person-1", "src-1", "medication", "pending", "Aspirin",
             "aspirin", None, None, timestamp, None, None),
        )
        connection.execute(
            "INSERT INTO candidate_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("cand-2", "person-1", "src-1", "medication", "confirmed", "Ibuprofen",
             "ibuprofen", "daily", None, timestamp, timestamp, None),
        )
        connection.execute(
            "INSERT INTO canonical_medication_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rec-1", "person-1", "cand-2", "src-1", "Ibuprofen", "ibuprofen",
             "daily", None, timestamp, 1),
        )
        connection.execute(
            "INSERT INTO timeline_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ev-1", "person-1", "rec-1", "src-1", "medication_confirmed",
             timestamp, "Medication confirmed: Ibuprofen"),
        )
        connection.execute(
            "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("v-1", "person-1", "Review", None, None, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO visit_briefs VALUES (?, ?, ?, ?, ?)",
            ("b-1", "v-1", "rev-1", timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO visit_brief_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rev-1", "b-1", 1, "deterministic_generation", None, 1, 1,
             json.dumps({"medications": []}), "# brief", "c" * 64, timestamp),
        )
        connection.execute(
            "INSERT INTO visit_brief_evidence_selections VALUES (?, ?, ?, ?, ?)",
            ("rev-1", 0, "rec-1", "src-1", json.dumps({"fingerprint": "x"})),
        )
        connection.execute("COMMIT")

    database.migrate()

    with database.connect() as connection:
        assert [row[0] for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()] == [1, 2, 3, 4, 5, 6, 7]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE id = 'rec-1'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_medication_details WHERE record_id = 'rec-1'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_medication_details WHERE candidate_id = 'cand-2'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_condition_details"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM candidate_lab_details"
        ).fetchone()[0] == 0
        assert tuple(connection.execute(
            "SELECT fact_type, event_type FROM timeline_events WHERE id = 'ev-1'"
        ).fetchone()) == ("medication", "medication_confirmed")
        assert connection.execute(
            "SELECT provenance_locator_json FROM candidate_facts WHERE id = 'cand-1'"
        ).fetchone()[0] == '{"kind":"structured_field","path":"medication"}'
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_brief_evidence_selections WHERE revision_id = 'rev-1'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_brief_revisions WHERE revision_id = 'rev-1'"
        ).fetchone()[0] == 1

    # The medication lifecycle remains fully usable against the v7 schema.
    from datetime import UTC, datetime as dt

    clock = lambda: dt(2026, 7, 26, 12, tzinfo=UTC)
    ids = iter(["src-new", "cand-new", "canon-new", "event-new", "spare-1"])
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=lambda: next(ids))
    lifecycle = MedicationLifecycleService(
        database, clock=clock, id_factory=lambda: next(ids), source_reader=sources.store.read
    )
    source = sources.register_manual_entry("person-1", "Omeprazole")
    candidate = lifecycle.create_candidate(
        person_id="person-1", source_id=source.id, display_name="Omeprazole"
    )
    record = lifecycle.confirm(candidate.id)
    assert record.is_active is True
    assert record.display_name == "Omeprazole"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE person_id = 'person-1'"
        ).fetchone()[0] == 2
