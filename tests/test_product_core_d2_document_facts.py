import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.agent.document_fact_trust import (
    DocumentFactTrustAdapter,
    encode_document_fact_question,
)
from app.agent.g2_product_repository import ProductCoreG2Repository
from app.agent.g2_runtime import G2Runtime
from app.agent.providers.contract import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
from app.agent_trust.identifiers import ACTION_REQUIREMENTS
from app.family_access.policy import CAREGIVER_OPTIONAL_SCOPES_V3
from app.product_core.sqlite import SQLiteDatabase


def test_d2_migration_creates_durable_runs_items_and_fingerprint_registry(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")

    database.migrate()

    with database.connect() as connection:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert versions == list(range(1, 12))
    assert {
        "document_fact_extraction_runs",
        "document_fact_extraction_items",
        "document_fact_extracted_facts",
    }.issubset(tables)


class _FakeProvider:
    def __init__(self) -> None:
        self.external = False
        self.calls = 0
        self.requests: list[ProviderExecutionRequest] = []

    answer: dict[str, Any] = {
        "medications": [
            {
                "page_number": 1,
                "evidence_quote": "Current medication: Aspirin 81 mg daily.",
                "display_name": "Aspirin",
                "schedule_text": "81 mg daily",
            }
        ],
        "conditions": [],
        "labs": [],
    }

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            "tests.document-facts",
            "external_http" if self.external else "self_hosted_http",
            "external_provider" if self.external else "local_only",
            "non_loopback" if self.external else "loopback",
            self.external,
            "test",
        )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        self.calls += 1
        self.requests.append(request)
        return ProviderExecutionResult(
            self.answer, self.descriptor.provider_id, self.descriptor.model_id, (), None
        )


def _select_person(client: TestClient, person_id: str = "person-1") -> None:
    response = client.put(
        "/api/family-access/v1/active-person", json={"person_id": person_id}
    )
    assert response.status_code == 204, response.text


def _login_caregiver(
    client: TestClient, optional_scopes: set[str], username: str
) -> tuple[str, str]:
    family_runtime = main_module.app.state.family_access_runtime
    owner_id = client.get("/api/family-access/v1/me").json()["actor"]["actor_id"]
    caregiver = family_runtime.service.create_local_actor(
        owner_id,
        username=username,
        display_name="Scope test caregiver",
        password="caregiver password value",
    )
    assignment = family_runtime.service.grant_assignment(
        owner_id,
        "person-1",
        caregiver.actor_id,
        role="caregiver",
        optional_scopes=optional_scopes,
        confirm_full_owner_access=False,
    )
    login = client.post(
        "/api/family-access/v1/login",
        json={"username": username, "password": "caregiver password value"},
    )
    assert login.status_code == 200, login.text
    csrf = client.cookies.get("opencare_csrf")
    assert csrf is not None
    client.headers.update({"origin": "http://testserver", "x-opencare-csrf": csrf})
    _select_person(client)
    return owner_id, assignment.assignment_id


def test_d2_local_provider_creates_pending_candidate_and_reuses_completed_run(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()["run_id"]
    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{run_id}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert provider.calls == 1


def test_d2_external_provider_requires_approval_and_decline_makes_no_call(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    provider.external = True
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "consent_required"
    run_id = prepared.json()["run_id"]
    declined = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{run_id}/consent",
        json={"decision": "decline"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert provider.calls == 0


def test_d21_external_approval_discloses_bounded_snapshot_and_executes_once(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    provider.external = True
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "../meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    payload = prepared.json()
    preview = payload["preview"]
    assert payload["status"] == "consent_required"
    assert preview["safe_filename"] == "meds.txt"
    assert preview["provider_id"] == "tests.document-facts"
    assert preview["model_id"] == "test"
    assert preview["external"] is True
    assert preview["page_count"] == 1
    assert preview["character_count"] == 40
    assert preview["enabled_categories"] == [
        "condition",
        "follow_up",
        "lab",
        "medication",
        "procedure",
        "recommendation",
    ]
    assert preview["retention"] == "provider_policy"
    approved = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/consent",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert provider.calls == 1


def test_d2_oversize_document_remains_stored_and_unavailable(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"x" * 60001,
        headers={"content-type": "text/plain", "x-opencare-filename": "large.txt"},
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "unavailable"
    assert prepared.json()["reason_code"] == "input_chars_limit_exceeded"
    assert provider.calls == 0


def test_d21_document_runtime_is_built_and_provider_receives_only_d1_page_text(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    runtime = main_module.app.state.product_core_runtime
    assert hasattr(main_module.app.state, "document_fact_g2_runtime")

    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    payload = prepared.json()
    assert payload["execution_id"]
    assert payload["input_text_hash"]
    assert payload["consent_id"]
    assert payload["envelope_id"].startswith("sha256:")

    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert provider.calls == 1
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.evidence == (
        {"page_number": 1, "text": "Current medication: Aspirin 81 mg daily."},
    )
    assert set(request.evidence[0]) == {"page_number", "text"}
    assert request.allowed_fields == (
        "condition",
        "follow_up",
        "lab",
        "medication",
        "procedure",
        "recommendation",
    )
    with runtime.database.connect() as connection:
        row = connection.execute(
            "SELECT execution_id, input_text_hash, consent_id, receipt_id "
            "FROM document_fact_extraction_runs"
        ).fetchone()
        assert row is not None
        assert row["execution_id"] == payload["execution_id"]
        assert row["consent_id"] == payload["consent_id"]
        assert row["receipt_id"] == executed.json()["receipt_id"]
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE document_fact_extraction_runs SET input_text_hash = ? WHERE run_id = ?",
                ("0" * 64, payload["run_id"]),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE document_fact_extraction_runs SET consent_id = NULL WHERE run_id = ?",
                (payload["run_id"],),
            )


def test_d21_document_envelope_and_provider_projection_use_exact_document_contract(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    extraction_id = uploaded.json()["document"]["extraction"]["extraction_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    payload = prepared.json()
    assert ACTION_REQUIREMENTS["document.extract_facts"] == (
        frozenset({"document.read"}),
        frozenset({"source.read"}),
    )
    token = product_core_client.cookies.get("opencare_session")
    assert token is not None
    family_runtime = main_module.app.state.family_access_runtime
    session = family_runtime.sessions.resolve(token)
    assert session is not None
    adapter = main_module.app.state.document_fact_trust
    envelope = adapter.build_envelope(
        actor_id=session.actor_id,
        credential_id=session.credential_id,
        person_id="person-1",
        purpose_id="document_fact_extraction",
        action_id="document.extract_facts",
        question=encode_document_fact_question(
            person_id="person-1",
            source_id=source_id,
            extraction_id=extraction_id,
            input_text_hash=payload["input_text_hash"],
            allowed_fact_types=payload["allowed_fact_types"],
            page_count=1,
            character_count=payload["character_count"],
        ),
    )
    assert envelope.resource_scopes == ["document.read"]
    assert envelope.allowed_tools == ["source.read"]
    assert envelope.evidence[0].resource_scope == "document.read"

    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    request = provider.requests[0]
    assert request.allowed_tools == ("source.read",)
    serialized_request = json.dumps(asdict(request), sort_keys=True, default=str)
    for forbidden in (
        "person-1",
        source_id,
        extraction_id,
        session.credential_id,
        "meds.txt",
        "C:\\",
    ):
        assert forbidden not in serialized_request
    assert request.evidence == (
        {"page_number": 1, "text": "Current medication: Aspirin 81 mg daily."},
    )


def test_d21_default_deterministic_provider_stays_unavailable_without_a_call(
    product_core_client: TestClient,
) -> None:
    main_module.app.state.agent_provider = main_module.DeterministicProvider()
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["status"] == "unavailable"
    assert prepared.json()["reason_code"] == "automatic_analysis_unavailable"


def test_d21_prepare_refuses_when_active_person_is_unset_and_does_not_bind_it(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    assert uploaded.status_code == 201, uploaded.text
    source_id = uploaded.json()["document"]["source_id"]
    token = product_core_client.cookies.get("opencare_session")
    assert token is not None
    family_runtime = main_module.app.state.family_access_runtime
    before = family_runtime.sessions.resolve(token)
    assert before is not None and before.active_person_id is None
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert response.status_code == 403
    after = family_runtime.sessions.resolve(token)
    assert after is not None and after.active_person_id is None
    assert provider.calls == 0


def test_d21_execution_restarts_from_canonical_consent_and_receipt_contract(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    payload = prepared.json()
    runtime = main_module.app.state.product_core_runtime
    family_runtime = main_module.app.state.family_access_runtime
    adapter = DocumentFactTrustAdapter(
        runtime, family_runtime.service, provider, clock=runtime.clock
    )
    main_module.app.state.document_fact_trust = adapter
    main_module.app.state.document_fact_g2_runtime = G2Runtime(
        family_runtime.sessions,
        prepare_envelope=adapter.build_envelope,
        revalidate=adapter.revalidate,
        provider=provider,
        repository=ProductCoreG2Repository(runtime.database),
        project=adapter.project,
        resolve_evidence=adapter.resolve_evidence,
        provider_request_builder=adapter.provider_request_builder,
        answer_validator=adapter.answer_validator,
        authorize_receipt=adapter.authorize_receipt,
        clock=runtime.clock,
    )
    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    assert provider.calls == 1


def test_d21_v10_binds_fact_run_to_execution_consent_and_receipt(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(document_fact_extraction_runs)"
        ).fetchall()}
        assert {"execution_id", "input_text_hash"}.issubset(columns)
        foreign_keys = {
            row[3]: row[2]
            for row in connection.execute(
                "PRAGMA foreign_key_list(document_fact_extraction_runs)"
            ).fetchall()
        }
        assert foreign_keys.get("consent_id") == "agent_disclosure_consents"
        assert foreign_keys.get("receipt_id") == "agent_execution_receipts"


def test_d21_v10_cross_binding_triggers_reject_provider_tampering(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()["run_id"]
    executed = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{run_id}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.connect() as connection:
        run = connection.execute(
            "SELECT consent_id, receipt_id FROM document_fact_extraction_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert run is not None
        consent = connection.execute(
            "SELECT provider_id, provider_descriptor_hash "
            "FROM agent_disclosure_consents WHERE consent_id = ?",
            (run["consent_id"],),
        ).fetchone()
        assert consent is not None
        original_provider_id = consent["provider_id"]
        original_provider_hash = consent["provider_descriptor_hash"]

        connection.execute(
            "UPDATE agent_disclosure_consents SET provider_id = ? WHERE consent_id = ?",
            ("tampered-provider", run["consent_id"]),
        )
        with pytest.raises(sqlite3.IntegrityError, match="consent_binding_mismatch"):
            connection.execute(
                "UPDATE document_fact_extraction_runs SET consent_id = consent_id WHERE run_id = ?",
                (run_id,),
            )
        connection.execute(
            "UPDATE agent_disclosure_consents SET provider_id = ? WHERE consent_id = ?",
            (original_provider_id, run["consent_id"]),
        )

        connection.execute(
            "UPDATE agent_disclosure_consents SET provider_descriptor_hash = ? "
            "WHERE consent_id = ?",
            ("0" * 64, run["consent_id"]),
        )
        with pytest.raises(sqlite3.IntegrityError, match="consent_binding_mismatch"):
            connection.execute(
                "UPDATE document_fact_extraction_runs SET consent_id = consent_id WHERE run_id = ?",
                (run_id,),
            )
        connection.execute(
            "UPDATE agent_disclosure_consents SET provider_descriptor_hash = ? "
            "WHERE consent_id = ?",
            (original_provider_hash, run["consent_id"]),
        )

        connection.execute(
            "UPDATE agent_execution_receipts SET provider_id = ? WHERE receipt_id = ?",
            ("tampered-provider", run["receipt_id"]),
        )
        with pytest.raises(sqlite3.IntegrityError, match="receipt_binding_mismatch"):
            connection.execute(
                "UPDATE document_fact_extraction_runs SET receipt_id = receipt_id WHERE run_id = ?",
                (run_id,),
            )


def test_d21_provider_descriptor_change_fails_closed_without_a_second_call(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()["run_id"]
    provider.external = True
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{run_id}/execute",
        json={},
    )
    assert response.status_code == 403
    assert provider.calls == 0
    with main_module.app.state.product_core_runtime.database.connect() as connection:
        assert connection.execute(
            "SELECT status FROM document_fact_extraction_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()["status"] == "consented"


def test_d21_removed_write_scope_fails_closed_without_provider_call(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    owner_id, assignment_id = _login_caregiver(
        product_core_client, set(CAREGIVER_OPTIONAL_SCOPES_V3), "scope-caregiver"
    )
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    main_module.app.state.family_access_runtime.service.revise_assignment(
        owner_id,
        "person-1",
        assignment_id,
        set(CAREGIVER_OPTIONAL_SCOPES_V3) - {"lab.write"},
    )
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{prepared.json()['run_id']}/execute",
        json={},
    )
    assert response.status_code == 403
    assert provider.calls == 0


def test_d21_added_write_scope_fails_closed_without_provider_call(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    owner_id, assignment_id = _login_caregiver(
        product_core_client,
        set(CAREGIVER_OPTIONAL_SCOPES_V3) - {"lab.write"},
        "scope-caregiver",
    )
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    main_module.app.state.family_access_runtime.service.revise_assignment(
        owner_id,
        "person-1",
        assignment_id,
        set(CAREGIVER_OPTIONAL_SCOPES_V3),
    )
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{prepared.json()['run_id']}/execute",
        json={},
    )
    assert response.status_code == 403
    assert provider.calls == 0


def test_d21_wrong_active_person_fails_closed_and_preserves_selection(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    _select_person(product_core_client, "person-2")
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{prepared.json()['run_id']}/execute",
        json={},
    )
    assert response.status_code == 403
    assert provider.calls == 0
    token = product_core_client.cookies.get("opencare_session")
    assert token is not None
    session = main_module.app.state.family_access_runtime.sessions.resolve(token)
    assert session is not None and session.active_person_id == "person-2"


def test_d21_canonical_consent_tampering_refuses_without_provider_call(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    payload = prepared.json()
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            "UPDATE agent_disclosure_consents SET consent_hash = ? WHERE consent_id = ?",
            ("0" * 64, payload["consent_id"]),
        )
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{payload['run_id']}/execute",
        json={},
    )
    assert response.status_code == 403
    assert provider.calls == 0


def test_d21_strict_schema_rejects_unexpected_provider_fields(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    provider.answer = {**provider.answer, "unexpected": True}
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    prepared = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/{prepared.json()['run_id']}/execute",
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["reason_code"] == "validation_failed"
    assert provider.calls == 1


def test_d22_historical_v1_run_remains_loadable_without_retroactive_categories(
    product_core_client: TestClient,
) -> None:
    _select_person(product_core_client)
    uploaded = product_core_client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=b"Current medication: Aspirin 81 mg daily.",
        headers={"content-type": "text/plain", "x-opencare-filename": "meds.txt"},
    )
    source_id = uploaded.json()["document"]["source_id"]
    extraction_id = uploaded.json()["document"]["extraction"]["extraction_id"]
    owner_id = product_core_client.get("/api/family-access/v1/me").json()["actor"][
        "actor_id"
    ]
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO document_fact_extraction_runs ("
            "run_id, person_id, source_id, extraction_id, actor_id, execution_id, "
            "input_text_hash, request_fingerprint, contract_version, status, "
            "allowed_fact_types_json, total_facts, valid_facts, invalid_facts, "
            "new_candidates, reused_candidates, external, created_at, updated_at, "
            "completed_at) VALUES ("
            "'run-v1-legacy', 'person-1', ?, ?, ?, 'exec-v1-legacy', "
            "?, ?, 'opencare-document-facts/1', 'completed', "
            "'[\"condition\", \"lab\", \"medication\"]', 0, 0, 0, 0, 0, 0, "
            "'2026-08-01T12:00:00+00:00', '2026-08-01T12:00:05+00:00', "
            "'2026-08-01T12:00:05+00:00')",
            (
                source_id,
                extraction_id,
                owner_id,
                "a" * 64,
                "b" * 64,
            ),
        )
    loaded = product_core_client.get(
        "/api/product-core/v1/people/person-1/documents/"
        f"{source_id}/fact-extractions/run-v1-legacy"
    )
    assert loaded.status_code == 200, loaded.text
    body = loaded.json()
    assert body["contract_version"] == "opencare-document-facts/1"
    assert body["status"] == "completed"
    assert body["allowed_fact_types"] == ["condition", "lab", "medication"]
    assert not {"procedure", "recommendation", "follow_up"} & set(
        body["allowed_fact_types"]
    )
    latest = product_core_client.get(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions"
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["contract_version"] == "opencare-document-facts/1"
    assert latest.json()["allowed_fact_types"] == ["condition", "lab", "medication"]
