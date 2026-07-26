import sqlite3
from pathlib import Path

import pytest

from app.product_core.migrations import Migration, MigrationRunner
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
        ] == [1]
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {
        "schema_migrations",
        "sources",
        "candidate_facts",
        "canonical_medication_records",
        "timeline_events",
    }.issubset(table_names)


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
