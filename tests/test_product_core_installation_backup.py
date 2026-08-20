from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.installation_backup import (
    InstallationBackupError,
    InstallationBackupService,
)
from app.product_core.models import Person
from app.product_core.persisted_visit_briefs import PersistedVisitBriefService
from app.product_core.services import (
    DocumentService,
    ImmutableSourceStore,
    MedicationLifecycleService,
    SourceService,
)
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visits import VisitPlanningService


def test_backup_and_offline_verify_create_a_complete_installation_artifact(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Synthetic profile",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "active-sources")
    source = sources.register_plain_text("person-1", "synthetic source")
    destination = tmp_path / "backup"

    service = InstallationBackupService(
        database.path,
        tmp_path / "active-sources",
        clock=lambda: now,
    )
    backup_report = service.backup(destination)
    verify_report = service.verify(destination)

    assert backup_report.valid is True
    assert verify_report.valid is True
    assert (destination / "COMPLETE").read_bytes() == b""
    manifest_bytes = (destination / "manifest.json").read_bytes()
    assert (destination / "manifest.sha256").read_bytes() == (
        hashlib.sha256(manifest_bytes).hexdigest().encode("ascii") + b"\n"
    )
    manifest = json.loads(manifest_bytes)
    assert manifest["format_version"] == 1
    assert manifest["product_core_schema_version"] == 9
    assert manifest["created_at"] == "2026-07-30T12:00:00+00:00"
    assert manifest["sources"][0]["source_id"] == source.id
    assert (destination / "sources" / source.id / "payload.bin").is_file()


def test_verify_uses_only_the_completed_backup_directory(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    service = InstallationBackupService(database.path, sources.store.source_dir)
    service.backup(destination)

    database.path.unlink()
    (sources.store.source_dir / source.relative_path).unlink()

    assert service.verify(destination).valid is True


def test_backup_rejects_changed_source_and_removes_staging(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    (sources.store.source_dir / source.relative_path).write_text("changed", encoding="utf-8")
    destination = tmp_path / "backup"

    with pytest.raises(InstallationBackupError, match="source_"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(destination)

    assert not destination.exists()
    assert not list(tmp_path.glob(".opencare-backup-*"))


def test_verify_rejects_missing_completion_marker(tmp_path: Path) -> None:
    database, sources, _source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    service = InstallationBackupService(database.path, sources.store.source_dir)
    service.backup(destination)
    (destination / "COMPLETE").unlink()

    with pytest.raises(InstallationBackupError, match="backup_incomplete"):
        service.verify(destination)


def test_backup_refuses_existing_destination_without_modifying_it(tmp_path: Path) -> None:
    database, sources, _source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("existing", encoding="utf-8")

    with pytest.raises(InstallationBackupError, match="destination_exists"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(destination)

    assert marker.read_text(encoding="utf-8") == "existing"


def test_backup_rejects_unsafe_persisted_source_id(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    with sqlite3.connect(database.path) as connection:
        connection.execute("UPDATE sources SET id = ? WHERE id = ?", ("../unsafe", source.id))

    with pytest.raises(InstallationBackupError, match="source_id_unsafe"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(
            tmp_path / "backup"
        )


def test_backup_rejects_source_path_escape(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE sources SET relative_path = ? WHERE id = ?",
            ("../outside.txt", source.id),
        )

    with pytest.raises(InstallationBackupError, match="source_path_unsafe"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(
            tmp_path / "backup"
        )


def test_backup_rejects_source_symlink(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    payload = sources.store.source_dir / source.relative_path
    target = tmp_path / "outside.txt"
    target.write_text("synthetic source", encoding="utf-8")
    payload.unlink()
    try:
        os.symlink(target, payload)
    except OSError:
        pytest.skip("symlinks are unavailable in this test environment")

    with pytest.raises(InstallationBackupError, match="symlink_rejected"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(
            tmp_path / "backup"
        )


def test_verify_rejects_manifest_checksum_mismatch_and_undeclared_file(tmp_path: Path) -> None:
    database, sources, _source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    service = InstallationBackupService(database.path, sources.store.source_dir)
    service.backup(destination)
    (destination / "manifest.sha256").write_bytes(b"0" * 64 + b"\n")

    with pytest.raises(InstallationBackupError, match="manifest_checksum_mismatch"):
        service.verify(destination)

    service.backup(tmp_path / "backup-2")
    (tmp_path / "backup-2" / "undeclared.bin").write_bytes(b"unexpected")
    with pytest.raises(InstallationBackupError, match="backup_layout_invalid"):
        service.verify(tmp_path / "backup-2")


def test_verify_rejects_changed_payload_and_snapshot_foreign_key_violation(
    tmp_path: Path,
) -> None:
    database, sources, source = _active_installation(tmp_path)
    service = InstallationBackupService(database.path, sources.store.source_dir)
    destination = tmp_path / "backup-fk"
    service.backup(destination)
    with sqlite3.connect(destination / "database.sqlite3") as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DELETE FROM people WHERE person_id = ?", ("person-1",))
    _refresh_database_payload_manifest(destination)

    with pytest.raises(InstallationBackupError, match="sqlite_foreign_key_failed"):
        service.verify(destination)

    destination = tmp_path / "backup-payload"
    service.backup(destination)
    payload = destination / "sources" / source.id / "payload.bin"
    payload.write_bytes(b"corrupt-source")
    with pytest.raises(InstallationBackupError, match="payload_.*mismatch"):
        service.verify(destination)


def test_backup_uses_the_sqlite_snapshot_and_excludes_unrelated_source_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, sources, source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    unrelated = sources.store.source_dir / "unrelated.txt"
    unrelated.write_text("not represented in SQLite", encoding="utf-8")
    from app.product_core import installation_backup

    original = installation_backup._create_sqlite_snapshot

    def snapshot_then_write(active: Path, target: Path) -> None:
        original(active, target)
        sources.register_plain_text("person-1", "committed after snapshot")

    monkeypatch.setattr(installation_backup, "_create_sqlite_snapshot", snapshot_then_write)
    InstallationBackupService(database.path, sources.store.source_dir).backup(destination)

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert [item["source_id"] for item in manifest["sources"]] == [source.id]
    assert not (destination / "sources" / "unrelated.txt").exists()


def test_backup_fails_closed_when_destination_appears_before_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, sources, _source = _active_installation(tmp_path)
    destination = tmp_path / "backup"
    from app.product_core import installation_backup

    original = installation_backup._create_complete_marker

    def create_marker_and_destination(staging: Path) -> None:
        original(staging)
        destination.mkdir()
        (destination / "existing.txt").write_text("keep", encoding="utf-8")

    monkeypatch.setattr(
        installation_backup,
        "_create_complete_marker",
        create_marker_and_destination,
    )

    with pytest.raises(InstallationBackupError, match="destination_appeared"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(destination)

    assert (destination / "existing.txt").read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".opencare-backup-*"))


def test_backup_includes_populated_lifecycle_and_brief_audit_rows(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    lifecycle = MedicationLifecycleService(database)
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Synthetic medication",
        schedule_text=None,
        note=None,
        provenance_locator={"kind": "span", "start": 0, "end": 16},
    )
    record = lifecycle.confirm(candidate.id)
    visits = VisitPlanningService(database)
    visit = visits.create_visit("person-1", title="Synthetic visit")
    visits.create_question(visit.visit_id, "Synthetic question")
    briefs = PersistedVisitBriefService(database, source_reader=sources.store.read)
    briefs.initialize(visit.visit_id)
    briefs.generate(
        visit.visit_id,
        selected_record_ids=[record.id],
        expected_current_revision_number=None,
    )
    destination = tmp_path / "backup"

    InstallationBackupService(database.path, sources.store.source_dir).backup(destination)

    with sqlite3.connect(destination / "database.sqlite3") as snapshot:
        assert snapshot.execute("SELECT COUNT(*) FROM visit_brief_audit_events").fetchone() == (2,)
        assert snapshot.execute("SELECT COUNT(*) FROM visit_questions").fetchone() == (1,)
    assert (destination / "sources" / source.id / "payload.bin").is_file()


def test_backup_rejects_corrupted_persisted_brief_before_completion(tmp_path: Path) -> None:
    database, sources, source = _active_installation(tmp_path)
    lifecycle = MedicationLifecycleService(database)
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Synthetic medication",
        schedule_text=None,
        note=None,
        provenance_locator={"kind": "span", "start": 0, "end": 16},
    )
    record = lifecycle.confirm(candidate.id)
    visits = VisitPlanningService(database)
    visit = visits.create_visit("person-1", title="Synthetic visit")
    briefs = PersistedVisitBriefService(database, source_reader=sources.store.read)
    briefs.initialize(visit.visit_id)
    revision = briefs.generate(
        visit.visit_id,
        selected_record_ids=[record.id],
        expected_current_revision_number=None,
    )
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE visit_brief_revisions SET content_hash = ? WHERE revision_id = ?",
            ("0" * 64, revision.revision_id),
        )

    with pytest.raises(InstallationBackupError, match="visit_brief_integrity_failed"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(
            tmp_path / "backup"
        )


def _active_installation(tmp_path: Path) -> tuple[SQLiteDatabase, SourceService, object]:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Synthetic profile",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "active-sources")
    source = sources.register_plain_text("person-1", "synthetic source")
    return database, sources, source


def _refresh_database_payload_manifest(destination: Path) -> None:
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = destination / "database.sqlite3"
    for payload in manifest["payloads"]:
        if payload["path"] == "database.sqlite3":
            payload["size_bytes"] = database.stat().st_size
            payload["sha256"] = hashlib.sha256(database.read_bytes()).hexdigest()
    raw = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest_path.write_bytes(raw)
    (destination / "manifest.sha256").write_bytes(
        hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n"
    )


@pytest.mark.parametrize("mutation", ["missing_page", "altered_page"])
def test_backup_rejects_missing_or_altered_document_extraction_pages(
    tmp_path: Path, mutation: str
) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    source_dir = tmp_path / "active-sources"
    document = DocumentService(database, ImmutableSourceStore(source_dir)).register(
        "person-1", b"document evidence", "text/plain"
    )
    with sqlite3.connect(database.path) as connection:
        connection.execute("DROP TRIGGER document_extraction_pages_immutable_delete")
        connection.execute("DROP TRIGGER document_extraction_pages_immutable_update")
        if mutation == "missing_page":
            connection.execute(
                "DELETE FROM document_extraction_pages WHERE extraction_id = ?",
                (document.extraction.extraction_id,),
            )
        else:
            connection.execute(
                """
                UPDATE document_extraction_pages
                SET normalized_text = 'altered', extracted_chars = 7
                WHERE extraction_id = ?
                """,
                (document.extraction.extraction_id,),
            )

    with pytest.raises(InstallationBackupError, match="document_extraction"):
        InstallationBackupService(database.path, source_dir).backup(tmp_path / "backup")
