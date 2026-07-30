import hashlib
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.errors import (
    SourceCorruptionError,
    SourcePublicationError,
    UnsafeSourcePathError,
)
from app.product_core.models import Person, Source
from app.product_core.services import SourceService
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


def make_source_service(tmp_path: Path, ids: SequenceIds | None = None) -> SourceService:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1")
    return SourceService(
        database,
        tmp_path / "sources",
        clock=FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC)),
        id_factory=ids or SequenceIds("source-1", "source-2"),
    )


def test_source_store_reads_fixed_recovery_payload_only_when_original_path_is_absent(
    tmp_path: Path,
) -> None:
    service = make_source_service(tmp_path)
    source = service.register_plain_text("person-1", "synthetic recovery payload")
    original = service.store.source_dir / source.relative_path
    recovered = service.store.source_dir / source.id / "payload.bin"
    recovered.parent.mkdir()
    original.replace(recovered)

    assert service.store.read(source) == b"synthetic recovery payload"

    original.write_bytes(b"corrupt original")
    with pytest.raises(SourceCorruptionError, match="source size mismatch"):
        service.store.read(source)


def test_source_store_never_uses_recovery_fallback_after_existing_original_link(
    tmp_path: Path,
) -> None:
    service = make_source_service(tmp_path)
    source = service.register_plain_text("person-1", "synthetic recovery payload")
    original = service.store.source_dir / source.relative_path
    recovered = service.store.source_dir / source.id / "payload.bin"
    recovered.parent.mkdir()
    recovered.write_bytes(b"synthetic recovery payload")
    original.unlink()
    try:
        os.symlink(recovered, original)
    except OSError:
        pytest.skip("symlinks are unavailable in this test environment")

    with pytest.raises(SourceCorruptionError, match="must not contain links"):
        service.store.read(source)


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


def test_manual_source_is_canonical_utf8_json_and_deduplicates(tmp_path: Path) -> None:
    service = make_source_service(tmp_path, SequenceIds("source-1", "unused"))

    first = service.register_manual_entry(
        "person-1",
        name="  Aspirin  ",
        schedule_text="  Morning  ",
        note="User entered",
    )
    second = service.register_manual_entry(
        "person-1",
        name="  Aspirin  ",
        schedule_text="  Morning  ",
        note="User entered",
    )

    assert first.id == second.id
    assert first.size_bytes == second.size_bytes
    payload = (tmp_path / "sources" / first.relative_path).read_bytes()
    assert payload == json.dumps(
        {
            "medication": {
                "name": "Aspirin",
                "note": "User entered",
                "schedule_text": "  Morning  ",
            },
            "schema_version": 1,
            "source_type": "manual_entry",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert first.content_hash == hashlib.sha256(payload).hexdigest()
    assert len(list((tmp_path / "sources").iterdir())) == 1


def test_concurrent_source_registration_returns_one_created_result(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1")
    first_service = SourceService(
        database,
        tmp_path / "sources",
        clock=FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC)),
        id_factory=SequenceIds("source-1"),
    )
    second_service = SourceService(
        database,
        tmp_path / "sources",
        clock=FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC)),
        id_factory=SequenceIds("source-2"),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda service: service.register_plain_text_result("person-1", "same"),
                [first_service, second_service],
            )
        )

    assert sorted(result.created for result in results) == [False, True]
    assert results[0].source.id == results[1].source.id
    assert len(list((tmp_path / "sources").iterdir())) == 1


def test_plain_text_preserves_exact_utf8_content(tmp_path: Path) -> None:
    service = make_source_service(tmp_path)
    content = "  Aspirin\tвечером\n"

    source = service.register_plain_text("person-1", content)

    assert (tmp_path / "sources" / source.relative_path).read_text(encoding="utf-8") == content
    assert source.media_type == "text/plain"


def test_source_read_detects_missing_and_altered_payloads(tmp_path: Path) -> None:
    service = make_source_service(tmp_path)
    source = service.register_plain_text("person-1", "original")
    path = tmp_path / "sources" / source.relative_path

    path.write_text("altered", encoding="utf-8")
    with pytest.raises(SourceCorruptionError):
        service.read(source.id)

    path.unlink()
    with pytest.raises(SourceCorruptionError):
        service.read(source.id)


def test_source_read_rejects_traversal_path(tmp_path: Path) -> None:
    service = make_source_service(tmp_path)
    source = service.register_plain_text("person-1", "original")
    database_path = tmp_path / "product.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE sources SET relative_path = ? WHERE id = ?",
            ("../outside.txt", source.id),
        )

    with pytest.raises(UnsafeSourcePathError):
        service.read(source.id)


def test_publication_collision_fails_without_overwriting_existing_file(tmp_path: Path) -> None:
    service = make_source_service(tmp_path, SequenceIds("same-id", "same-id"))
    first = service.register_plain_text("person-1", "first")

    with pytest.raises(SourcePublicationError):
        service.register_plain_text("person-1", "different")

    assert (tmp_path / "sources" / first.relative_path).read_text(encoding="utf-8") == "first"


def test_failed_database_insert_compensates_newly_published_file(tmp_path: Path) -> None:
    service = make_source_service(tmp_path)
    database_path = tmp_path / "product.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_source_insert
            BEFORE INSERT ON sources
            BEGIN
                SELECT RAISE(ABORT, 'forced source insert failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        service.register_plain_text("person-1", "new")

    assert not list((tmp_path / "sources").iterdir())


def test_invalid_timestamp_compensates_newly_published_file(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    seed_people(database, "person-1")
    service = SourceService(
        database,
        tmp_path / "sources",
        clock=FixedClock(datetime(2026, 7, 26, 10)),
        id_factory=SequenceIds("source-1"),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        service.register_plain_text("person-1", "new")

    assert not list((tmp_path / "sources").iterdir())


def test_source_model_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Source(
            id="source-1",
            person_id="person-1",
            source_type="plain_text",
            relative_path="source-1.txt",
            content_hash="a" * 64,
            size_bytes=1,
            media_type="text/plain",
            created_at=datetime(2026, 7, 26, 10),
            provenance={},
        )
