"""D2.2 export/backup guarantees: v6 vault collections, contract identity, v11 round trip."""

from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest

from app.family_access.policy import (
    CAREGIVER_BASE_SCOPES_V3,
    OWNER_SCOPES_V4,
    POLICY_VERSION,
    V3_POLICY_VERSION,
    infer_generation,
    valid_role_scopes,
)
from app.product_core.installation_backup import (
    InstallationBackupError,
    InstallationBackupService,
)
from app.product_core.installation_recovery import (
    InstallationRecoveryService,
    verify_recovered_installation,
)
from app.product_core.migrations import PRODUCT_MIGRATIONS, MigrationRunner
from app.product_core.models import (
    CandidateFact,
    CanonicalRecord,
    FollowUpCandidateDetail,
    Person,
    ProcedureCandidateDetail,
    RecommendationCandidateDetail,
    TimelineEvent,
    normalize_fact_name,
)
from app.product_core.portable_vault_export import (
    PORTABLE_VAULT_FORMAT_VERSION,
    PRODUCT_CORE_SCHEMA_VERSION,
    PortableVaultExportService,
)
from app.product_core.services import DocumentService, ImmutableSourceStore
from app.product_core.sqlite import SQLiteDatabase

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)
V1_CONTRACT = "opencare-document-facts/1"
V2_CONTRACT = "opencare-document-facts/2"


def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BlockedSocket(socket.socket):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("export/backup/recovery attempted network access")

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("export/backup/recovery attempted network access")

    monkeypatch.setattr(socket, "socket", _BlockedSocket)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def _migrated(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    return database


def _seed_facts(database: SQLiteDatabase, source_dir: Path) -> None:
    """Seed new-family candidates/records plus a v1 + v2 run on one document."""
    source_dir.mkdir(parents=True, exist_ok=True)
    manual_payload = b'{"entry_method":"manual"}'
    (source_dir / "src-man.json").write_bytes(manual_payload)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=NOW,
                updated_at=NOW,
                is_active=True,
            )
        )
        uow.connection.execute(
            "INSERT INTO actors VALUES (?, ?, ?, 'active', ?, NULL, NULL)",
            ("actor-1", "actor-1", "Actor One", NOW.isoformat()),
        )
        uow.connection.execute(
            "INSERT INTO sources (id, person_id, source_type, relative_path,"
            " content_hash, size_bytes, media_type, created_at, provenance_json)"
            " VALUES ('src-man','person-1','manual_entry','src-man.json',?,?,?,?,?)",
            (
                hashlib.sha256(manual_payload).hexdigest(),
                len(manual_payload),
                "application/json",
                NOW.isoformat(),
                '{"entry_method":"manual"}',
            ),
        )
        uow.candidates.insert(
            CandidateFact(
                id="cand-proc",
                person_id="person-1",
                source_id="src-man",
                fact_type="procedure",
                detail=ProcedureCandidateDetail(
                    display_name="CT scan",
                    normalized_name=normalize_fact_name("CT scan"),
                    status_text="scheduled",
                    date_text="October",
                    note="pending review",
                ),
                created_at=NOW,
            )
        )
        uow.candidates.insert(
            CandidateFact(
                id="cand-rec",
                person_id="person-1",
                source_id="src-man",
                fact_type="recommendation",
                status="confirmed",
                detail=RecommendationCandidateDetail(
                    instruction_text="Swim daily",
                    normalized_instruction=normalize_fact_name("Swim daily"),
                    context_text="cardiology plan",
                ),
                created_at=NOW,
                reviewed_at=NOW,
            )
        )
        uow.canonical_records.insert(
            CanonicalRecord(
                id="rec-rec",
                person_id="person-1",
                candidate_id="cand-rec",
                source_id="src-man",
                fact_type="recommendation",
                detail=RecommendationCandidateDetail(
                    instruction_text="Swim daily",
                    normalized_instruction=normalize_fact_name("Swim daily"),
                    context_text="cardiology plan",
                ),
                confirmed_at=NOW,
                is_active=True,
            )
        )
        uow.timeline_events.insert(
            TimelineEvent(
                id="ev-rec",
                person_id="person-1",
                canonical_record_id="rec-rec",
                source_id="src-man",
                fact_type="recommendation",
                event_type="recommendation_confirmed",
                event_at=NOW,
                title="Recommendation recorded: Swim daily",
            )
        )
        uow.candidates.insert(
            CandidateFact(
                id="cand-fu",
                person_id="person-1",
                source_id="src-man",
                fact_type="follow_up",
                status="rejected",
                detail=FollowUpCandidateDetail(
                    action_text="Scan review",
                    normalized_action=normalize_fact_name("Scan review"),
                    timing_text="6 weeks",
                ),
                created_at=NOW,
                reviewed_at=NOW,
            )
        )
    documents = DocumentService(database, ImmutableSourceStore(source_dir))
    registered = documents.register(
        "person-1", b"Current medication: Aspirin 81 mg daily.", "text/plain"
    )
    with database.uow() as uow:
        assert uow.connection is not None
        extraction_id = registered.extraction.extraction_id
        for run_id, contract, allowed in (
            ("run-v1", V1_CONTRACT, ["medication", "condition", "lab"]),
            (
                "run-v2",
                V2_CONTRACT,
                ["medication", "condition", "lab", "procedure", "recommendation", "follow_up"],
            ),
        ):
            uow.connection.execute(
                "INSERT INTO document_fact_extraction_runs (run_id, person_id, source_id,"
                " extraction_id, actor_id, execution_id, input_text_hash,"
                " request_fingerprint, contract_version, status, allowed_fact_types_json,"
                " external, created_at, updated_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,'completed',?,0,?,?,?)",
                (
                    run_id,
                    "person-1",
                    registered.source.id,
                    extraction_id,
                    "actor-1",
                    f"exec-{run_id}",
                    "d" * 64,
                    hashlib.sha256(run_id.encode()).hexdigest(),
                    contract,
                    json.dumps(allowed),
                    NOW.isoformat(),
                    NOW.isoformat(),
                    NOW.isoformat(),
                ),
            )


def _load_vault(content: bytes) -> dict[str, object]:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        return json.loads(archive.read("vault.json"))


def test_export_v6_includes_new_family_detail_collections(tmp_path: Path) -> None:
    database = _migrated(tmp_path)
    _seed_facts(database, tmp_path / "sources")

    exported = PortableVaultExportService(database, ImmutableSourceStore(tmp_path / "sources"))
    vault = _load_vault(exported.export("person-1").zip_bytes)

    assert vault["candidate_procedure_details"] == [
        {
            "candidate_id": "cand-proc",
            "display_name": "CT scan",
            "normalized_name": "ct scan",
            "status_text": "scheduled",
            "date_text": "October",
            "note": "pending review",
        }
    ]
    assert vault["candidate_recommendation_details"] == [
        {
            "candidate_id": "cand-rec",
            "instruction_text": "Swim daily",
            "normalized_instruction": "swim daily",
            "context_text": "cardiology plan",
            "note": None,
        }
    ]
    assert vault["candidate_follow_up_details"] == [
        {
            "candidate_id": "cand-fu",
            "action_text": "Scan review",
            "normalized_action": "scan review",
            "timing_text": "6 weeks",
            "destination_text": None,
            "note": None,
        }
    ]
    assert vault["canonical_recommendation_details"] == [
        {
            "record_id": "rec-rec",
            "instruction_text": "Swim daily",
            "normalized_instruction": "swim daily",
            "context_text": "cardiology plan",
            "note": None,
        }
    ]
    assert vault["canonical_procedure_details"] == []
    assert vault["canonical_follow_up_details"] == []


def test_export_preserves_run_contract_identity_without_widening(tmp_path: Path) -> None:
    database = _migrated(tmp_path)
    _seed_facts(database, tmp_path / "sources")

    vault = _load_vault(
        PortableVaultExportService(
            database, ImmutableSourceStore(tmp_path / "sources")
        ).export("person-1").zip_bytes
    )
    runs = {item["run_id"]: item for item in vault["document_fact_extraction_runs"]}  # type: ignore[index]
    assert runs["run-v1"]["contract_version"] == V1_CONTRACT
    assert runs["run-v2"]["contract_version"] == V2_CONTRACT
    assert json.loads(str(runs["run-v1"]["allowed_fact_types_json"])) == [
        "medication",
        "condition",
        "lab",
    ]
    assert json.loads(str(runs["run-v2"]["allowed_fact_types_json"])) == [
        "medication",
        "condition",
        "lab",
        "procedure",
        "recommendation",
        "follow_up",
    ]


def test_format_and_schema_version_pins() -> None:
    assert PORTABLE_VAULT_FORMAT_VERSION == 6
    assert PRODUCT_CORE_SCHEMA_VERSION == 11
    assert PRODUCT_MIGRATIONS[-1].version == 11


def _seed_family_access(database: SQLiteDatabase) -> None:
    with database.uow() as uow:
        assert uow.connection is not None
        uow.connection.execute(
            "INSERT INTO actors VALUES (?, ?, ?, 'active', ?, NULL, NULL)",
            ("actor-2", "actor-2", "Actor Two", NOW.isoformat()),
        )
        for actor_id, credential_id in (("actor-1", "cred-1"), ("actor-2", "cred-2")):
            uow.connection.execute(
                "INSERT INTO actor_credentials VALUES (?, ?, 'local_password', 'scrypt', 1, "
                "x'00000000000000000000000000000000', x'" + "0" * 128 + "', ?, NULL, NULL)",
                (credential_id, actor_id, NOW.isoformat()),
            )
        uow.connection.execute(
            "INSERT INTO installation_admin_assignments VALUES (?, ?, ?, 1, ?, NULL, NULL, NULL)",
            ("admin-1", "actor-1", "actor-1", NOW.isoformat()),
        )
        owner_scopes = json.dumps(sorted(OWNER_SCOPES_V4))
        caregiver_scopes = json.dumps(sorted(CAREGIVER_BASE_SCOPES_V3))
        uow.connection.execute(
            "INSERT INTO person_access_consent_history VALUES (?, 'grant', ?, ?, ?, 'owner',"
            " ?, 'bootstrap_owner_grant', ?)",
            ("consent-1", "actor-1", "actor-1", "person-1", owner_scopes, NOW.isoformat()),
        )
        uow.connection.execute(
            "INSERT INTO person_access_consent_history VALUES (?, 'grant', ?, ?, ?, 'caregiver',"
            " ?, 'caregiver_grant', ?)",
            ("consent-2", "actor-1", "actor-2", "person-1", caregiver_scopes, NOW.isoformat()),
        )
        uow.connection.execute(
            "INSERT INTO person_access_assignments VALUES (?, ?, ?, 'owner', ?, ?, ?, 1, ?,"
            " NULL, NULL, NULL, ?)",
            (
                "assignment-1",
                "actor-1",
                "person-1",
                owner_scopes,
                "consent-1",
                "actor-1",
                NOW.isoformat(),
                POLICY_VERSION,
            ),
        )
        uow.connection.execute(
            "INSERT INTO person_access_assignments VALUES (?, ?, ?, 'caregiver', ?, ?, ?, 1, ?,"
            " NULL, NULL, NULL, ?)",
            (
                "assignment-2",
                "actor-2",
                "person-1",
                caregiver_scopes,
                "consent-2",
                "actor-1",
                NOW.isoformat(),
                V3_POLICY_VERSION,
            ),
        )


COMPARE_TABLES = (
    "candidate_facts",
    "canonical_records",
    "timeline_events",
    "candidate_procedure_details",
    "candidate_recommendation_details",
    "candidate_follow_up_details",
    "canonical_procedure_details",
    "canonical_recommendation_details",
    "canonical_follow_up_details",
    "document_fact_extraction_runs",
    "person_access_assignments",
    "person_access_consent_history",
)


def _dump_tables(path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(path) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in COMPARE_TABLES
        }


def test_backup_verify_recover_roundtrip_for_d2_2_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _migrated(tmp_path)
    _seed_facts(database, tmp_path / "sources")
    _seed_family_access(database)
    with sqlite3.connect(database.path) as connection:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
    assert versions == list(range(1, 12))

    pre = _dump_tables(database.path)
    service = InstallationBackupService(database.path, tmp_path / "sources", clock=lambda: NOW)
    destination = tmp_path / "backup"
    _no_network(monkeypatch)
    backup_report = service.backup(destination)
    assert backup_report.valid is True
    assert backup_report.product_core_schema_version == 11
    verify_report = service.verify(destination)
    assert verify_report.valid is True

    target = tmp_path / "recovered"
    recovered = InstallationRecoveryService(clock=lambda: NOW).recover(
        destination, target, confirm_maintenance=True
    )
    assert recovered.valid is True
    assert recovered.product_core_schema_version == 11
    checked = verify_recovered_installation(target)
    assert checked.valid is True

    post = _dump_tables(target / "database.sqlite3")
    assert post == pre
    with sqlite3.connect(target / "database.sqlite3") as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            connection.execute(
                "SELECT title FROM timeline_events WHERE id = 'ev-rec'"
            ).fetchone()[0]
            == "Recommendation recorded: Swim daily"
        )
        runs = dict(
            connection.execute(
                "SELECT run_id, contract_version FROM document_fact_extraction_runs"
            ).fetchall()
        )
        stored = {
            role: (json.loads(scopes_json), generation)
            for role, scopes_json, generation in connection.execute(
                "SELECT role, scopes_json, scope_generation FROM person_access_assignments"
                " ORDER BY role"
            )
        }
    assert runs == {"run-v1": V1_CONTRACT, "run-v2": V2_CONTRACT}
    # The stored v4/v3 generation mix survives the pure-restore round trip
    # and each stored scope set still infers to its original generation.
    assert stored["owner"][1] == POLICY_VERSION
    assert infer_generation(stored["owner"][0]) == POLICY_VERSION
    assert valid_role_scopes("owner", stored["owner"][0])
    assert stored["caregiver"][1] == V3_POLICY_VERSION
    assert infer_generation(stored["caregiver"][0]) == V3_POLICY_VERSION
    assert valid_role_scopes("caregiver", stored["caregiver"][0])


def test_backup_rejects_v10_shaped_snapshot(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "v10.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:10]).migrate()
    now = NOW
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
    (tmp_path / "sources").mkdir()

    with pytest.raises(InstallationBackupError, match="unsupported_schema_version"):
        InstallationBackupService(database.path, tmp_path / "sources", clock=lambda: NOW).backup(
            tmp_path / "backup"
        )
