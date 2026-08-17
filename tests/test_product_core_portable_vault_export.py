from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest

from app.product_core.errors import (
    SourceCorruptionError,
    UnsafeSourcePathError,
    VisitBriefIntegrityError,
)
from app.product_core.models import Person
from app.product_core.persisted_visit_briefs import PersistedVisitBriefService
from app.product_core.portable_vault_export import PortableVaultExportService
from app.product_core.services import (
    MedicationLifecycleService,
    SourceService,
)
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visits import VisitPlanningService


def test_empty_person_export_has_canonical_bundle_and_manifest_checksum(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    timestamp = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=timestamp,
                updated_at=timestamp,
                is_active=True,
            )
        )

    exported = PortableVaultExportService(database, tmp_path / "sources").export("person-1")

    with zipfile.ZipFile(BytesIO(exported.zip_bytes)) as archive:
        assert archive.namelist() == ["manifest.json", "manifest.sha256", "vault.json"]
        manifest = archive.read("manifest.json")
        vault = json.loads(archive.read("vault.json"))
        assert archive.read("manifest.sha256").decode("ascii") == hashlib.sha256(
            manifest
        ).hexdigest()
    assert vault["format_version"] == 3
    assert vault["person"]["person_id"] == "person-1"
    assert vault["sources"] == []
    assert "relative_path" not in manifest.decode("utf-8")


def test_populated_export_is_person_scoped_and_has_stable_canonical_payloads(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    timestamp = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        for person_id in ("person-1", "person-2"):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=person_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                    is_active=True,
                )
            )
    source_service = SourceService(database, tmp_path / "sources")
    lifecycle = MedicationLifecycleService(database)
    source = source_service.register_manual_entry("person-1", "Aspirin")
    unrelated = source_service.register_plain_text("person-2", "unrelated")
    candidate = lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Aspirin",
        schedule_text=None,
        note=None,
    )
    record = lifecycle.confirm(candidate.id)
    visits = VisitPlanningService(database)
    visit = visits.create_visit("person-1", title="Cardiology")
    question = visits.create_question(visit.visit_id, question_text="What should I ask?")
    briefs = PersistedVisitBriefService(database, source_reader=source_service.store.read)
    briefs.initialize(visit.visit_id)
    revision = briefs.generate(
        visit.visit_id,
        selected_record_ids=[record.id],
        expected_current_revision_number=None,
    )
    exporter = PortableVaultExportService(database, source_service.store)

    first = exporter.export("person-1")
    second = exporter.export("person-1")

    assert first.vault_json == second.vault_json
    assert first.manifest_json == second.manifest_json
    with zipfile.ZipFile(BytesIO(first.zip_bytes)) as archive:
        names = archive.namelist()
        vault_bytes = archive.read("vault.json")
        vault = json.loads(vault_bytes)
        manifest = json.loads(archive.read("manifest.json"))
        assert names == [
            "manifest.json",
            "manifest.sha256",
            "vault.json",
            f"sources/{source.id}/payload.bin",
        ]
        assert f"sources/{unrelated.id}/payload.bin" not in names
        assert archive.read(f"sources/{source.id}/payload.bin") == source_service.read(source.id)
        assert manifest["payloads"][0] == {
            "path": "vault.json",
            "sha256": hashlib.sha256(vault_bytes).hexdigest(),
            "size_bytes": len(vault_bytes),
        }
    assert vault["person"]["person_id"] == "person-1"
    assert vault["canonical_records"][0]["canonical_record_id"] == record.id
    assert vault["visit_questions"][0]["question_id"] == question.question_id
    assert vault["visit_brief_revisions"][0]["revision_number"] == 1
    serialized = first.vault_json.decode("utf-8")
    assert unrelated.id not in serialized
    assert "relative_path" not in serialized
    assert "visit_brief_audit_events" not in serialized
    assert '"fact_type":"medication"' in serialized
    assert '"provenance_locator"' in serialized

    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE visit_brief_revisions SET content_hash = ? WHERE revision_id = ?",
            ("0" * 64, revision.revision_id),
        )
    with pytest.raises(VisitBriefIntegrityError):
        exporter.export("person-1")


def test_export_fails_closed_when_reached_source_is_missing(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    timestamp = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=timestamp,
                updated_at=timestamp,
                is_active=True,
            )
        )
    source_service = SourceService(database, tmp_path / "sources")
    source = source_service.register_plain_text("person-1", "original")
    lifecycle = MedicationLifecycleService(database)
    lifecycle.create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Aspirin",
        schedule_text=None,
        note=None,
        provenance_locator={"kind": "span", "start": 0, "end": 8},
    )
    (tmp_path / "sources" / source.relative_path).unlink()

    with pytest.raises(SourceCorruptionError):
        PortableVaultExportService(database, source_service.store).export("person-1")


@pytest.mark.parametrize(
    ("mutation", "error_type"),
    [
        ("size", SourceCorruptionError),
        ("path", UnsafeSourcePathError),
        ("non_regular", SourceCorruptionError),
    ],
)
def test_export_rejects_invalid_reached_source_storage(
    tmp_path: Path,
    mutation: str,
    error_type: type[Exception],
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    timestamp = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=timestamp,
                updated_at=timestamp,
                is_active=True,
            )
        )
    source_service = SourceService(database, tmp_path / "sources")
    source = source_service.register_plain_text("person-1", "original")
    MedicationLifecycleService(database).create_candidate(
        person_id="person-1",
        source_id=source.id,
        display_name="Aspirin",
        schedule_text=None,
        note=None,
        provenance_locator={"kind": "span", "start": 0, "end": 8},
    )
    path = tmp_path / "sources" / source.relative_path
    if mutation == "size":
        path.write_text("a longer altered payload", encoding="utf-8")
    elif mutation == "path":
        with sqlite3.connect(database.path) as connection:
            connection.execute(
                "UPDATE sources SET relative_path = ? WHERE id = ?",
                ("../outside.txt", source.id),
            )
    else:
        path.unlink()
        path.mkdir()

    with pytest.raises(error_type):
        PortableVaultExportService(database, source_service.store).export("person-1")
