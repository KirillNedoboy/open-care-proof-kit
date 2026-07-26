from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from app.product_core.migrations import MigrationRunner
from app.product_core.repositories import (
    SQLiteCandidateRepository,
    SQLiteCanonicalRepository,
    SQLiteSourceRepository,
    SQLiteTimelineRepository,
)


class SQLiteDatabase:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def migrate(self) -> None:
        MigrationRunner(self.connect).migrate()

    def uow(self) -> UnitOfWork:
        return UnitOfWork(self)


class UnitOfWork:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self.connection: sqlite3.Connection | None = None
        self.sources: SQLiteSourceRepository
        self.candidates: SQLiteCandidateRepository
        self.canonical_records: SQLiteCanonicalRepository
        self.timeline_events: SQLiteTimelineRepository

    def __enter__(self) -> Self:
        self.connection = self.database.connect()
        self.connection.execute("BEGIN")
        self.sources = SQLiteSourceRepository(self.connection)
        self.candidates = SQLiteCandidateRepository(self.connection)
        self.canonical_records = SQLiteCanonicalRepository(self.connection)
        self.timeline_events = SQLiteTimelineRepository(self.connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.connection is not None
        try:
            if exc_type is None:
                try:
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
