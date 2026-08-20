"""P1 security hardening: provenance integrity, person isolation, and
transactional review atomicity for the generalized evidence lifecycle.

Each test maps to a design acceptance item (design §24 Wrong Person scenario,
§25 security counters, §16 migration plan, §22 export/recovery)."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.errors import PersonMismatchError, SourceCorruptionError
from app.product_core.installation_backup import InstallationBackupService
from app.product_core.installation_recovery import (
    InstallationRecoveryService,
    verify_recovered_installation,
)
from app.product_core.models import (
    ConditionCandidateInput,
    LabCandidateInput,
    Person,
)
from app.product_core.portable_vault_export import (
    PORTABLE_VAULT_FORMAT_VERSION,
    PortableVaultExportService,
)
from app.product_core.services import MedicationLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visits import VisitPlanningService


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"p1-{self.value}"


def _setup(
    tmp_path: Path,
    *person_ids: str,
) -> tuple[
    SQLiteDatabase,
    SourceService,
    MedicationLifecycleService,
    SequenceIds,
    FixedClock,
]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    ids = SequenceIds()
    with database.uow() as uow:
        for person_id in person_ids:
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=f"Profile {person_id}",
                    created_at=clock(),
                    updated_at=clock(),
                    is_active=True,
                )
            )
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(
        database,
        clock=clock,
        id_factory=ids,
        source_reader=sources.store.read,
    )
    return database, sources, lifecycle, ids, clock


def _confirmed_condition(
    database: SQLiteDatabase,
    sources: SourceService,
    lifecycle: MedicationLifecycleService,
    person_id: str,
    name: str = "Asthma",
) -> tuple[str, str]:
    source = sources.register_structured_manual_entry(
        person_id, "condition", {"display_name": name}
    )
    candidate = lifecycle.create_fact_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name=name),
    )
    record = lifecycle.confirm(candidate.id)
    return record.id, candidate.id


def _confirmed_lab(
    database: SQLiteDatabase,
    sources: SourceService,
    lifecycle: MedicationLifecycleService,
    person_id: str,
    test_name: str = "Hemoglobin",
) -> tuple[str, str]:
    source = sources.register_structured_manual_entry(
        person_id, "lab", {"test_name": test_name, "result_text": "13.8"}
    )
    candidate = lifecycle.create_fact_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(test_name=test_name, result_text="13.8"),
    )
    record = lifecycle.confirm(candidate.id)
    return record.id, candidate.id


# --------------------------------------------------------------------------- #
# Item 5: candidate creation with a source belonging to another Person is
# rejected (service-level PersonMismatchError; the API boundary hides foreign
# sources as 404 and is covered in test_product_core_access_enforcement).
# --------------------------------------------------------------------------- #
def test_foreign_source_candidate_creation_raises_person_mismatch(
    tmp_path: Path,
) -> None:
    database, sources, lifecycle, _, _ = _setup(tmp_path, "person-1", "person-2")
    source = sources.register_structured_manual_entry(
        "person-2", "condition", {"display_name": "Asthma"}
    )

    with pytest.raises(PersonMismatchError):
        lifecycle.create_fact_candidate(
            person_id="person-1",
            source_id=source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="Asthma"),
        )


# --------------------------------------------------------------------------- #
# Items 9/10: confirmation atomicity for condition and lab — a failing
# timeline insert rolls back the canonical record, the candidate status flip,
# and the typed detail.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fact_type", ["condition", "lab"])
def test_condition_and_lab_confirmation_rolls_back_on_timeline_failure(
    tmp_path: Path,
    fact_type: str,
) -> None:
    database, sources, lifecycle, _, _ = _setup(tmp_path, "person-1")
    if fact_type == "condition":
        source = sources.register_structured_manual_entry(
            "person-1", "condition", {"display_name": "Asthma"}
        )
        candidate = lifecycle.create_fact_candidate(
            person_id="person-1",
            source_id=source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="Asthma"),
        )
    else:
        source = sources.register_structured_manual_entry(
            "person-1", "lab", {"test_name": "Hemoglobin", "result_text": "13.8"}
        )
        candidate = lifecycle.create_fact_candidate(
            person_id="person-1",
            source_id=source.id,
            fact_type="lab",
            detail_input=LabCandidateInput(test_name="Hemoglobin", result_text="13.8"),
        )
    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_timeline_insert
            BEFORE INSERT ON timeline_events
            BEGIN
                SELECT RAISE(ABORT, 'forced timeline failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        lifecycle.confirm(candidate.id)

    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM timeline_events"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT status, reviewed_at FROM candidate_facts WHERE id = ?",
            (candidate.id,),
        ).fetchone()[0] == "pending"
        detail_table = {
            "condition": "candidate_condition_details",
            "lab": "candidate_lab_details",
        }[fact_type]
        assert connection.execute(
            f"SELECT COUNT(*) FROM {detail_table} WHERE candidate_id = ?",
            (candidate.id,),
        ).fetchone()[0] == 1  # the candidate's own detail row is untouched


# --------------------------------------------------------------------------- #
# Item 15: source corruption fails closed on a provenance-dependent read
# during confirmation of a condition/lab candidate.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fact_type", ["condition", "lab"])
def test_source_corruption_fails_closed_on_condition_and_lab_confirm(
    tmp_path: Path,
    fact_type: str,
) -> None:
    database, sources, lifecycle, _, _ = _setup(tmp_path, "person-1")
    if fact_type == "condition":
        source = sources.register_structured_manual_entry(
            "person-1", "condition", {"display_name": "Asthma"}
        )
        candidate = lifecycle.create_fact_candidate(
            person_id="person-1",
            source_id=source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="Asthma"),
        )
    else:
        source = sources.register_structured_manual_entry(
            "person-1", "lab", {"test_name": "Hemoglobin", "result_text": "13.8"}
        )
        candidate = lifecycle.create_fact_candidate(
            person_id="person-1",
            source_id=source.id,
            fact_type="lab",
            detail_input=LabCandidateInput(test_name="Hemoglobin", result_text="13.8"),
        )

    # Corrupt the immutable source payload: hash/size verification must fail.
    path = Path(sources.store.source_dir) / source.relative_path
    path.write_text("altered payload", encoding="utf-8")

    with pytest.raises(SourceCorruptionError):
        lifecycle.confirm(candidate.id)

    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT status FROM candidate_facts WHERE id = ?",
            (candidate.id,),
        ).fetchone()[0] == "pending"


# --------------------------------------------------------------------------- #
# Item 16: timeline Person isolation.
# --------------------------------------------------------------------------- #
def test_timeline_person_isolation(tmp_path: Path) -> None:
    database, sources, lifecycle, _, _ = _setup(tmp_path, "person-1", "person-2")
    _confirmed_condition(database, sources, lifecycle, "person-1")
    _confirmed_lab(database, sources, lifecycle, "person-1")

    events_one = lifecycle.list_timeline("person-1")
    events_two = lifecycle.list_timeline("person-2")

    assert len(events_one) == 2
    assert {event.fact_type for event in events_one} == {"condition", "lab"}
    assert events_two == []


# --------------------------------------------------------------------------- #
# Item 18: export Person isolation for condition/lab entities + v3 round trip.
# --------------------------------------------------------------------------- #
def test_export_person_isolation_for_condition_and_lab_and_v3_round_trip(
    tmp_path: Path,
) -> None:
    database, sources, lifecycle, _, _ = _setup(tmp_path, "person-1", "person-2")
    condition_record, _ = _confirmed_condition(
        database, sources, lifecycle, "person-1", "Asthma"
    )
    lab_record, _ = _confirmed_lab(database, sources, lifecycle, "person-1")
    _confirmed_lab(database, sources, lifecycle, "person-2", "Glucose")

    exporter = PortableVaultExportService(database, sources.store)
    person_one = json.loads(exporter.export("person-1").vault_json)
    person_two = json.loads(exporter.export("person-2").vault_json)

    assert person_one["format_version"] == PORTABLE_VAULT_FORMAT_VERSION
    assert {
        record["canonical_record_id"] for record in person_one["canonical_records"]
    } == {condition_record, lab_record}
    assert person_one["canonical_condition_details"]
    assert person_one["canonical_lab_details"]
    assert person_one["candidate_facts"]
    # Person-2's export contains ONLY person-2's own entities: its own lab
    # record (Glucose), never person-1's condition/lab records.
    person_two_record_ids = {
        record["canonical_record_id"] for record in person_two["canonical_records"]
    }
    assert len(person_two["canonical_records"]) == 1
    assert {condition_record, lab_record}.isdisjoint(person_two_record_ids)
    assert all(
        record["person_id"] == "person-2" for record in person_two["canonical_records"]
    )
    assert person_two["canonical_condition_details"] == []
    assert all(
        detail["test_name"] == "Glucose"
        for detail in person_two["canonical_lab_details"]
    )
    assert person_two["person"]["person_id"] == "person-2"

    # Deterministic round trip: two exports of the same Person are identical.
    assert exporter.export("person-1").vault_json == exporter.export("person-1").vault_json


# --------------------------------------------------------------------------- #
# Item 19a: backup/recovery preservation — populated v7 (medication + condition
# + lab + visit + assignment + G2 receipt) round trips through recover.
# --------------------------------------------------------------------------- #
def test_backup_recovery_preserves_populated_v7_p1_state(tmp_path: Path) -> None:
    from app.family_access.service import FamilyAccessService
    from app.product_core.persisted_visit_briefs import PersistedVisitBriefService

    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    ids = SequenceIds()
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=clock(),
                updated_at=clock(),
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "active-sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(
        database, clock=clock, id_factory=ids, source_reader=sources.store.read
    )
    med_source = sources.register_manual_entry("person-1", "Aspirin")
    med_candidate = lifecycle.create_candidate(
        person_id="person-1", source_id=med_source.id, display_name="Aspirin"
    )
    med_record = lifecycle.confirm(med_candidate.id)
    condition_record, _ = _confirmed_condition(database, sources, lifecycle, "person-1")
    lab_record, _ = _confirmed_lab(database, sources, lifecycle, "person-1")
    visits = VisitPlanningService(database, clock=clock, id_factory=ids)
    visit = visits.create_visit("person-1", title="Review")
    briefs = PersistedVisitBriefService(
        database, clock=clock, id_factory=ids, source_reader=sources.store.read
    )
    briefs.initialize(visit.visit_id)
    briefs.generate(
        visit.visit_id,
        selected_record_ids=[med_record.id, condition_record, lab_record],
        expected_current_revision_number=None,
    )
    family = FamilyAccessService(
        database, clock=clock, id_factory=ids
    )
    owner = family.bootstrap(
        username="owner",
        display_name="Owner",
        password="owner password value",
        person_ids=("person-1",),
        confirm_full_owner_access=True,
    )
    # G2 consent + receipt row.
    from datetime import timedelta

    receipt_id = "sha256:" + "1" * 64
    consent_id = "p1-consent"
    execution_id = "p1-exec"
    envelope_id = "sha256:" + "0" * 64
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            INSERT INTO agent_disclosure_consents (
                consent_id, execution_id, actor_id, person_id, purpose, action,
                envelope_id, provider_id, provider_descriptor_hash,
                disclosure_metadata_json, policy_version, consented_at,
                expires_at, consent_hash, metadata_json
            ) VALUES (?, ?, ?, ?, 'purpose', 'action', ?, 'provider', ?, '{}',
                      'family-access-v2', ?, ?, ?, '{}')
            """,
            (
                consent_id,
                execution_id,
                owner.actor_id,
                "person-1",
                envelope_id,
                "d" * 64,
                clock().isoformat(),
                (clock() + timedelta(hours=1)).isoformat(),
                "e" * 64,
            ),
        )
        uow.connection.execute(
            """
            INSERT INTO agent_execution_receipts (
                receipt_id, execution_id, consent_id, actor_id, person_id,
                envelope_id, provider_id, status, started_at, completed_at,
                used_evidence_ids_json, used_tools_json, output_sha256,
                mutation_attempted, reason_codes_json, receipt_sha256, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'provider', 'completed', ?, ?,
                      '[]', '[]', ?, 0, '[]', ?, '{}')
            """,
            (
                receipt_id,
                execution_id,
                consent_id,
                owner.actor_id,
                "person-1",
                envelope_id,
                clock().isoformat(),
                (clock() + timedelta(seconds=1)).isoformat(),
                "2" * 64,
                "f" * 64,
            ),
        )

    backup = InstallationBackupService(
        database.path, tmp_path / "active-sources", clock=lambda: clock()
    )
    destination = tmp_path / "backup"
    report = backup.backup(destination)
    assert report.valid is True
    assert report.product_core_schema_version == 8

    target = tmp_path / "recovered"
    recovery = InstallationRecoveryService(clock=lambda: clock())
    recovery.recover(destination, target, confirm_maintenance=True)
    recovered = verify_recovered_installation(target)
    assert recovered.valid is True

    with sqlite3.connect(target / "database.sqlite3") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'condition'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'lab'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_medication_details"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_condition_details"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_lab_details"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_brief_evidence_selections"
        ).fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM person_access_assignments WHERE is_active = 1"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_disclosure_consents"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM agent_execution_receipts"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


# --------------------------------------------------------------------------- #
# Item 19b: a populated v6 database migrates to v7 and then survives
# backup -> recover with its P1 state intact.
# --------------------------------------------------------------------------- #
def test_v6_to_v7_backup_recovers_preserving_state(tmp_path: Path) -> None:
    from app.product_core.migrations import PRODUCT_MIGRATIONS, MigrationRunner

    active = tmp_path / "active.sqlite3"
    database = SQLiteDatabase(active)
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
            ("cand-1", "person-1", "src-1", "medication", "confirmed", "Ibuprofen",
             "ibuprofen", "daily", None, timestamp, timestamp, None),
        )
        connection.execute(
            "INSERT INTO canonical_medication_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rec-1", "person-1", "cand-1", "src-1", "Ibuprofen", "ibuprofen",
             "daily", None, timestamp, 1),
        )
        connection.execute(
            "INSERT INTO timeline_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("ev-1", "person-1", "rec-1", "src-1", "medication_confirmed",
             timestamp, "Medication confirmed: Ibuprofen"),
        )
        connection.execute("COMMIT")
    database.migrate()

    # Write the v6-era source payload so the backup can verify and copy it.
    import hashlib

    payload = b"ibuprofen recorded source"
    source_dir = tmp_path / "active-sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "src-1.json").write_bytes(payload)
    with database.connect() as connection:
        connection.execute(
            "UPDATE sources SET content_hash = ?, size_bytes = ? WHERE id = 'src-1'",
            (hashlib.sha256(payload).hexdigest(), len(payload)),
        )

    # Seed P1 entities on the v7 database, then back up and recover.
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    ids = SequenceIds()
    sources = SourceService(database, tmp_path / "active-sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(
        database, clock=clock, id_factory=ids, source_reader=sources.store.read
    )
    _confirmed_condition(database, sources, lifecycle, "person-1", "Asthma")

    backup = InstallationBackupService(
        database.path, tmp_path / "active-sources", clock=lambda: clock()
    )
    destination = tmp_path / "backup"
    assert backup.backup(destination).valid is True

    target = tmp_path / "recovered"
    InstallationRecoveryService(clock=lambda: clock()).recover(
        destination, target, confirm_maintenance=True
    )
    recovered = verify_recovered_installation(target)
    assert recovered.valid is True
    assert recovered.product_core_schema_version == 8
    with sqlite3.connect(target / "database.sqlite3") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'medication'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'condition'"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
