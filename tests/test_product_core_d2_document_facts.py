from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import app.main as main_module
from app.agent.providers.contract import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
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

    assert versions == list(range(1, 11))
    assert {
        "document_fact_extraction_runs",
        "document_fact_extraction_items",
        "document_fact_extracted_facts",
    }.issubset(tables)


class _FakeProvider:
    def __init__(self) -> None:
        self.external = False
        self.calls = 0

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
        return ProviderExecutionResult(
            self.answer, self.descriptor.provider_id, self.descriptor.model_id, (), None
        )


def test_d2_local_provider_creates_pending_candidate_and_reuses_completed_run(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
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


def test_d2_oversize_document_remains_stored_and_unavailable(
    product_core_client: TestClient,
) -> None:
    provider = _FakeProvider()
    main_module.app.state.agent_provider = provider
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
