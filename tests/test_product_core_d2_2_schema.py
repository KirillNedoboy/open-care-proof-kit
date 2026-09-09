"""D2.2 schema tests: v10->v11 preservation, CHECK constraints, detail alignment."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.product_core.migrations import PRODUCT_MIGRATIONS, MigrationRunner
from app.product_core.models import (
    CandidateFact,
    ProcedureCandidateDetail,
)
from app.product_core.sqlite import SQLiteDatabase

TS = "2026-08-09T10:00:00+00:00"
DETAIL_TABLES_V11 = (
    "candidate_procedure_details",
    "candidate_recommendation_details",
    "candidate_follow_up_details",
    "canonical_procedure_details",
    "canonical_recommendation_details",
    "canonical_follow_up_details",
)


def _text_page(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_v10(database: SQLiteDatabase) -> None:
    """Populate a v10 database the way the repo's smoke migrations tests do."""
    page_text = "Procedure performed: Example endoscopy on 1 January 2026."
    with database.connect() as connection:
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("person-1", "Ada", None, TS, TS, 1),
        )
        connection.execute(
            "INSERT INTO sources (id, person_id, source_type, relative_path, content_hash,"
            " size_bytes, media_type, created_at, provenance_json,"
            " original_filename, document_kind)"
            " VALUES (?, ?, 'manual_entry', 'src-1.json', ?, 1, 'application/json',"
            " ?, ?, NULL, NULL)",
            ("src-1", "person-1", "a" * 64, TS, json.dumps({"entry_method": "manual"})),
        )
        connection.execute(
            "INSERT INTO sources (id, person_id, source_type, relative_path, content_hash,"
            " size_bytes, media_type, created_at, provenance_json,"
            " original_filename, document_kind)"
            " VALUES (?, ?, 'document', 'src-doc.txt', ?, 1, 'text/plain',"
            " ?, ?, 'src-doc.txt', 'text')",
            ("src-doc", "person-1", "b" * 64, TS, json.dumps({"kind": "document"})),
        )
        connection.execute(
            "INSERT INTO actors (actor_id, username_normalized, display_name, status,"
            " created_at) VALUES ('actor-owner', 'owner', 'Owner', 'active', ?)",
            (TS,),
        )
        connection.execute(
            "INSERT INTO document_extractions (extraction_id, source_id, person_id,"
            " extractor, extractor_version, status, text_hash, total_chars, page_count,"
            " extracted_at) VALUES ('ext-1', 'src-doc', 'person-1', 'd1', 'v1', 'complete',"
            " ?, ?, 1, ?)",
            (_text_page(page_text), len(page_text), TS),
        )
        connection.execute(
            "INSERT INTO document_extraction_pages (extraction_id, source_id, person_id,"
            " page_number, normalized_text, decoded_content_bytes, extracted_chars,"
            " page_hash) VALUES ('ext-1', 'src-doc', 'person-1', 1, ?, ?, ?, ?)",
            (page_text, len(page_text.encode()), len(page_text), _text_page(page_text)),
        )
        connection.execute(
            "INSERT INTO candidate_facts (id, person_id, source_id, fact_type, status,"
            " created_at, reviewed_at, predecessor_candidate_id, provenance_locator_json)"
            " VALUES ('cand-med', 'person-1', 'src-1', 'medication', 'confirmed', ?,"
            " ?, NULL, '{\"kind\":\"structured_field\",\"path\":\"medication\"}')",
            (TS, TS),
        )
        connection.execute(
            "INSERT INTO candidate_medication_details (candidate_id, display_name,"
            " normalized_name, schedule_text, note) VALUES ('cand-med', 'Aspirin',"
            " 'aspirin', 'daily', NULL)",
        )
        connection.execute(
            "INSERT INTO canonical_records (id, person_id, candidate_id, source_id,"
            " fact_type, confirmed_at, is_active, superseded_by_record_id) VALUES"
            " ('rec-1', 'person-1', 'cand-med', 'src-1', 'medication', ?, 1, NULL)",
            (TS,),
        )
        connection.execute(
            "INSERT INTO canonical_medication_details (record_id, display_name,"
            " normalized_name, schedule_text, note) VALUES ('rec-1', 'Aspirin',"
            " 'aspirin', 'daily', NULL)",
        )
        connection.execute(
            "INSERT INTO timeline_events (id, person_id, canonical_record_id, source_id,"
            " fact_type, event_type, event_at, title) VALUES ('ev-1', 'person-1', 'rec-1',"
            " 'src-1', 'medication', 'medication_confirmed', ?, 'Medication confirmed:"
            " Aspirin')",
            (TS,),
        )
        connection.execute(
            "INSERT INTO document_fact_extraction_runs (run_id, person_id, source_id,"
            " extraction_id, actor_id, execution_id, input_text_hash,"
            " request_fingerprint, contract_version, status, allowed_fact_types_json,"
            " created_at, updated_at, completed_at, total_facts, valid_facts,"
            " invalid_facts, new_candidates, reused_candidates, external)"
            " VALUES ('run-1', 'person-1', 'src-doc', 'ext-1', 'actor-owner', 'exec-1',"
            " ?, ?, 'opencare-document-facts/1', 'completed', '[\"medication\","
            " \"condition\", \"lab\"]', ?, ?, ?, 1, 1, 0, 1, 0, 0)",
            (_text_page(page_text), "c" * 64, TS, TS, TS),
        )
        connection.execute(
            "INSERT INTO document_fact_extraction_items (item_id, run_id, person_id,"
            " source_id, extraction_id, ordinal, fact_type, payload_json, quote,"
            " page_number, start_codepoint, end_codepoint, selected_text_sha256,"
            " validation_status, candidate_id, candidate_fingerprint, created_at)"
            " VALUES ('item-1', 'run-1', 'person-1', 'src-doc', 'ext-1', 0,"
            " 'medication', '{\"display_name\": \"Aspirin\"}', 'Aspirin', 1, 0, 7, ?, "
            "'valid', 'cand-med', ?, ?)",
            (hashlib.sha256(b"Aspirin").hexdigest(), "d" * 64, TS),
        )
        connection.execute(
            "INSERT INTO document_fact_extracted_facts (candidate_fingerprint,"
            " person_id, source_id, fact_type, candidate_id, created_at) VALUES"
            " (?, 'person-1', 'src-doc', 'medication', 'cand-med', ?)",
            ("d" * 64, TS),
        )
        connection.execute("COMMIT")


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' AND name <> 'schema_migrations'"
        ).fetchall()
    }


def _snapshot(
    connection: sqlite3.Connection, tables: set[str]
) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: sorted(tuple(row) for row in connection.execute(f"SELECT * FROM {table}"))
        for table in sorted(tables)
    }


def test_v10_to_v11_preserves_every_existing_row(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:10]).migrate()
    _seed_v10(database)
    with database.connect() as connection:
        before_tables = _table_names(connection)
        before = _snapshot(connection, before_tables)
    database.migrate()
    with database.connect() as connection:
        after_tables = _table_names(connection)
        after = _snapshot(connection, before_tables)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    # Every pre-existing table keeps identical rows byte-for-byte.
    assert after == before
    # The six v11 typed detail tables exist and are empty.
    assert set(DETAIL_TABLES_V11).issubset(after_tables)
    for table in DETAIL_TABLES_V11:
        assert after.get(table, []) == [] or table not in before_tables


def test_v11_fact_type_checks_accept_six_types(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:10]).migrate()
    _seed_v10(database)
    database.migrate()
    with database.connect() as connection:
        for index, fact_type in enumerate(("procedure", "recommendation", "follow_up")):
            connection.execute(
                "INSERT INTO candidate_facts (id, person_id, source_id, fact_type, status,"
                " created_at) VALUES (?, 'person-1', 'src-1', ?, 'pending', ?)",
                (f"cand-{fact_type}", fact_type, TS),
            )
            assert index is not None
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO candidate_facts (id, person_id, source_id, fact_type, status,"
                " created_at) VALUES ('cand-bogus', 'person-1', 'src-1', 'bogus',"
                " 'pending', ?)",
                (TS,),
            )
        # The extracted-facts registry accepts the new types too.
        connection.execute(
            "INSERT INTO document_fact_extracted_facts (candidate_fingerprint,"
            " person_id, source_id, fact_type, candidate_id, created_at) VALUES"
            " (?, 'person-1', 'src-1', 'procedure', 'cand-procedure', ?)",
            ("e" * 64, TS),
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM document_fact_extracted_facts WHERE fact_type ="
                " 'procedure'"
            ).fetchone()[0]
            == 1
        )


def test_v11_contract_version_check_accepts_v1_v2_rejects_v3(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:10]).migrate()
    _seed_v10(database)
    database.migrate()
    base = (
        "INSERT INTO document_fact_extraction_runs (run_id, person_id, source_id,"
        " extraction_id, actor_id, execution_id, input_text_hash,"
        " request_fingerprint, contract_version, status, allowed_fact_types_json,"
        " created_at, updated_at, external) VALUES (?, 'person-1', 'src-doc', 'ext-1',"
        " 'actor-owner', ?, ?, ?, ?, 'prepared', '[\"procedure\"]', ?, ?, 0)"
    )
    with database.connect() as connection:
        for index, (run_id, version) in enumerate(
            (
                ("run-v1b", "opencare-document-facts/1"),
                ("run-v2", "opencare-document-facts/2"),
            )
        ):
            # Distinct request fingerprints: the active-request unique index is
            # partial over prepared..completed statuses.
            connection.execute(
                base,
                (run_id, f"exec-{run_id}", "a" * 64, f"{index + 1}" * 64, version, TS, TS),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                base,
                ("run-v3", "exec-run-v3", "c" * 64, "d" * 64, "opencare-document-facts/3", TS, TS),
            )


def test_v11_detail_rows_are_fk_bound_to_generic_rows(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:10]).migrate()
    _seed_v10(database)
    database.migrate()
    with database.connect() as connection:
        # SQLiteDatabase.connect enforces PRAGMA foreign_keys=ON.
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO candidate_procedure_details (candidate_id, display_name,"
                " normalized_name) VALUES ('does-not-exist', 'Appendectomy',"
                " 'appendectomy')"
            )
        connection.execute(
            "INSERT INTO candidate_facts (id, person_id, source_id, fact_type, status,"
            " created_at) VALUES ('cand-proc', 'person-1', 'src-1', 'procedure',"
            " 'pending', ?)",
            (TS,),
        )
        connection.execute(
            "INSERT INTO candidate_procedure_details (candidate_id, display_name,"
            " normalized_name, status_text, date_text, note) VALUES ('cand-proc',"
            " 'Appendectomy', 'appendectomy', 'performed', '12 March 2025', NULL)"
        )
        assert (
            connection.execute(
                "SELECT normalized_name FROM candidate_procedure_details WHERE"
                " candidate_id = 'cand-proc'"
            ).fetchone()[0]
            == "appendectomy"
        )
        with pytest.raises(sqlite3.IntegrityError):
            # 1:1: the same candidate cannot hold two procedure detail rows.
            connection.execute(
                "INSERT INTO canonical_procedure_details (record_id, display_name,"
                " normalized_name) VALUES ('no-such-record', 'X', 'x')"
            )


def test_detail_model_type_alignment(tmp_path: Path) -> None:
    detail = ProcedureCandidateDetail(
        display_name="Appendectomy",
        normalized_name="appendectomy",
        status_text="performed",
        date_text="12 March 2025",
    )
    from datetime import UTC, datetime

    now = datetime(2026, 8, 9, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CandidateFact(
            id="cand-1",
            person_id="person-1",
            source_id="src-1",
            fact_type="lab",
            detail=detail,
            created_at=now,
        )
    aligned = CandidateFact(
        id="cand-1",
        person_id="person-1",
        source_id="src-1",
        fact_type="procedure",
        detail=detail,
        created_at=now,
    )
    assert aligned.detail is detail


def test_candidate_detail_union_parses_six_shapes() -> None:
    from pydantic import TypeAdapter

    from app.product_core.models import (
        ConditionCandidateDetail,
        FollowUpCandidateDetail,
        LabCandidateDetail,
        MedicationCandidateDetail,
        RecommendationCandidateDetail,
    )

    # Discriminated by the distinct required field sets (extra="forbid").
    adapter = TypeAdapter(
        MedicationCandidateDetail
        | ConditionCandidateDetail
        | LabCandidateDetail
        | ProcedureCandidateDetail
        | RecommendationCandidateDetail
        | FollowUpCandidateDetail
    )
    cases: list[tuple[dict[str, object], type[object]]] = [
        (
            {"display_name": "Aspirin", "normalized_name": "aspirin", "schedule_text": "daily"},
            MedicationCandidateDetail,
        ),
        (
            {
                "display_name": "Hypertension",
                "normalized_name": "hypertension",
                "onset_date": "2024-01-02",
            },
            ConditionCandidateDetail,
        ),
        (
            {"test_name": "CBC", "normalized_test_name": "cbc", "result_text": "12"},
            LabCandidateDetail,
        ),
        (
            {
                "display_name": "Appendectomy",
                "normalized_name": "appendectomy",
                "date_text": "12 March 2025",
            },
            ProcedureCandidateDetail,
        ),
        (
            {
                "instruction_text": "Limit dietary sodium.",
                "normalized_instruction": "limit dietary sodium.",
            },
            RecommendationCandidateDetail,
        ),
        (
            {
                "action_text": "Repeat CBC",
                "normalized_action": "repeat cbc",
                "timing_text": "in 2 weeks",
            },
            FollowUpCandidateDetail,
        ),
    ]
    for payload, expected in cases:
        parsed = adapter.validate_python(payload)
        assert isinstance(parsed, expected), payload
