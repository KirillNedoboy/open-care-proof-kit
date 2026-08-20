from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core import installation_recovery
from app.product_core.installation_backup import InstallationBackupService
from app.product_core.installation_recovery import (
    InstallationRecoveryError,
    InstallationRecoveryService,
    verify_recovered_installation,
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


def test_preflight_is_read_only_and_recovery_reconstructs_an_absent_installation(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 31, 12, tzinfo=UTC)
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
    source_service = SourceService(database, tmp_path / "active-sources")
    source = source_service.register_plain_text("person-1", "synthetic source")
    backup = tmp_path / "backup"
    InstallationBackupService(database.path, source_service.store.source_dir).backup(backup)
    target = tmp_path / "recovered"

    service = InstallationRecoveryService(clock=lambda: now)
    preflight = service.preflight(backup, target)

    assert preflight.valid is True
    assert not target.exists()
    assert not list(tmp_path.glob(".opencare-recovery-*"))

    recovered = service.recover(backup, target, confirm_maintenance=True)

    assert recovered.valid is True
    assert (target / "database.sqlite3").read_bytes() == (backup / "database.sqlite3").read_bytes()
    assert (target / "sources" / source.id / "payload.bin").read_bytes() == b"synthetic source"
    report = json.loads((target / "RECOVERY_REPORT.json").read_text(encoding="utf-8"))
    assert report["target_activation_result"] == "activated"
    assert report["verification_results"] == {
        "post_activation_installation": "valid",
        "staged_installation": "valid",
    }
    assert verify_recovered_installation(target).valid is True


def test_recovery_replaces_an_existing_empty_target_and_uses_fixed_source_layout(
    tmp_path: Path,
) -> None:
    database, source_service, source, backup = _backup_with_source(tmp_path)
    target = tmp_path / "recovered"
    target.mkdir()

    InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)

    recovered_database = SQLiteDatabase(target / "database.sqlite3")
    with recovered_database.uow() as uow:
        recovered_source = uow.sources.get(source.id)
    assert SourceService(recovered_database, target / "sources").store.read(recovered_source) == (
        b"synthetic source"
    )
    assert (backup / "database.sqlite3").read_bytes() == (target / "database.sqlite3").read_bytes()


def test_preflight_refuses_populated_target_without_modifying_it(tmp_path: Path) -> None:
    _database, _sources, _source, backup = _backup_with_source(tmp_path)
    target = tmp_path / "populated"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(InstallationRecoveryError, match="target_not_empty"):
        InstallationRecoveryService().preflight(backup, target)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_recovery_post_activation_failure_restores_absent_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _database, _sources, _source, backup = _backup_with_source(tmp_path)
    target = tmp_path / "recovered"
    original = installation_recovery._verify_recovered_installation

    def fail_after_activation(path: Path, *, activation: str):
        if activation == "activated":
            raise InstallationRecoveryError("post_activation_verification_failed")
        return original(path, activation=activation)

    monkeypatch.setattr(
        installation_recovery,
        "_verify_recovered_installation",
        fail_after_activation,
    )

    with pytest.raises(InstallationRecoveryError, match="post_activation_verification_failed"):
        InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)

    assert not target.exists()
    assert not list(tmp_path.glob(".opencare-recovery-*"))


def test_preflight_blocks_only_exact_abandoned_recovery_artifacts(tmp_path: Path) -> None:
    _database, _sources, _source, backup = _backup_with_source(tmp_path)
    target = tmp_path / "recovered"
    unrelated = tmp_path / ".opencare-recovery-staging-not-a-tool-artifact"
    unrelated.mkdir()
    assert InstallationRecoveryService().preflight(backup, target).valid is True
    abandoned = tmp_path / ".opencare-recovery-staging-0123456789abcdef0123456789abcdef"
    abandoned.mkdir()

    with pytest.raises(InstallationRecoveryError, match="abandoned_recovery_artifact"):
        InstallationRecoveryService().preflight(backup, target)


def test_recovery_preserves_the_required_empty_sources_directory(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    sources = SourceService(database, tmp_path / "active-sources")
    backup = tmp_path / "backup"
    InstallationBackupService(database.path, sources.store.source_dir).backup(backup)
    target = tmp_path / "recovered"

    InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)

    assert (target / "sources").is_dir()
    assert verify_recovered_installation(target).valid is True


def test_recovered_verifier_rejects_unsafe_persisted_source_path(tmp_path: Path) -> None:
    _database, _sources, source, backup = _backup_with_source(tmp_path)
    target = tmp_path / "recovered"
    InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)
    with sqlite3.connect(target / "database.sqlite3") as connection:
        connection.execute(
            "UPDATE sources SET relative_path = ? WHERE id = ?",
            ("../unsafe", source.id),
        )

    with pytest.raises(InstallationRecoveryError, match="source_path_unsafe"):
        verify_recovered_installation(target)


def test_recovery_preserves_lifecycle_brief_hashes_and_backup_audit_rows(tmp_path: Path) -> None:
    database, sources, source, _backup = _backup_with_source(tmp_path)
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
    backup = tmp_path / "populated-backup"
    InstallationBackupService(database.path, sources.store.source_dir).backup(backup)
    target = tmp_path / "recovered"

    InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)

    assert verify_recovered_installation(target).valid is True
    with sqlite3.connect(target / "database.sqlite3") as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM canonical_records").fetchone()
            == (1,)
        )
        assert connection.execute("SELECT COUNT(*) FROM visit_brief_revisions").fetchone() == (1,)
        assert (
            connection.execute("SELECT COUNT(*) FROM visit_brief_audit_events").fetchone() == (2,)
        )


def _backup_with_source(tmp_path: Path) -> tuple[SQLiteDatabase, SourceService, object, Path]:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 31, 12, tzinfo=UTC)
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
    backup = tmp_path / "backup"
    InstallationBackupService(database.path, sources.store.source_dir).backup(backup)
    return database, sources, source, backup


def test_recovery_round_trips_document_payload_and_extraction_identity(
    tmp_path: Path,
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
    registered = DocumentService(database, ImmutableSourceStore(source_dir)).register(
        "person-1",
        b"preserved extraction text",
        "text/plain",
        original_filename="evidence.txt",
    )
    backup = tmp_path / "backup"
    InstallationBackupService(database.path, source_dir).backup(backup)
    target = tmp_path / "recovered"

    InstallationRecoveryService().recover(backup, target, confirm_maintenance=True)

    assert (
        target / "sources" / registered.source.id / "payload.bin"
    ).read_bytes() == b"preserved extraction text"
    recovered = SQLiteDatabase(target / "database.sqlite3")
    with recovered.uow() as uow:
        source = uow.sources.get(registered.source.id)
        extraction = uow.document_extractions.get(registered.extraction.extraction_id)
        pages = uow.document_extractions.list_pages(registered.extraction.extraction_id)
    assert source is not None
    assert source.original_filename == "evidence.txt"
    assert source.document_kind == "text"
    assert extraction == registered.extraction
    assert [page.normalized_text for page in pages] == ["preserved extraction text"]
