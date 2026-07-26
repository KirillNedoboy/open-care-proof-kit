from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from app.product_core.runtime import create_product_core_runtime
from tests.product_core_api_support import json_headers


def test_imports_are_side_effect_free_in_fresh_subprocess(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "product.sqlite3"
    source_dir = tmp_path / "nested" / "sources"
    environment = os.environ.copy()
    environment["OPENCARE_PRODUCT_DB_PATH"] = str(database_path)
    environment["OPENCARE_SOURCE_DIR"] = str(source_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main, app.product_core.api, app.product_core.runtime",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert not database_path.exists()
    assert not source_dir.exists()


def test_manual_source_creation_and_deduplication(product_core_client: TestClient) -> None:
    first = product_core_client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": "person-1",
            "medication": {
                "display_name": "  Aspirin  ",
                "schedule_text": "morning",
            },
        },
        headers=json_headers(),
    )
    second = product_core_client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": "person-1",
            "medication": {
                "display_name": "Aspirin",
                "schedule_text": "morning",
            },
        },
        headers=json_headers(),
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["source"] == second.json()["source"]
    assert "relative_path" not in first.text
    assert "product.sqlite" not in first.text


def test_plain_text_source_preserves_hash_and_enforces_utf8_limit(
    product_core_client: TestClient,
) -> None:
    response = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "вечером"},
        headers=json_headers(),
    )
    oversized = product_core_client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "person-1", "content": "я" * 131_073},
        headers=json_headers(),
    )

    assert response.status_code == 201
    assert response.json()["source"]["media_type"] == "text/plain"
    assert len(response.json()["source"]["content_hash"]) == 64
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "request_validation_failed"
    assert "вечером" not in oversized.text


def test_product_core_openapi_is_stable_and_public_only(product_core_client: TestClient) -> None:
    schema = product_core_client.get("/openapi.json").json()
    paths = [path for path in schema["paths"] if path.startswith("/api/product-core/v1")]
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert len(paths) == 11
    assert len(operation_ids) == len(set(operation_ids))
    assert all("relative_path" not in str(value) for value in schema.values())
    assert "SourceRegistrationResponse" in schema["components"]["schemas"]


def test_startup_migration_failure_does_not_publish_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()

    def failing_factory(settings: object) -> object:
        runtime = create_product_core_runtime(settings)  # type: ignore[arg-type]

        def fail_migration() -> None:
            raise RuntimeError("migration failure")

        runtime.database.migrate = fail_migration
        return runtime

    main_module.app.state.product_core_runtime_factory = failing_factory
    try:
        with pytest.raises(RuntimeError, match="migration failure"), TestClient(main_module.app):
            pass
        assert not hasattr(main_module.app.state, "product_core_runtime")
    finally:
        if hasattr(main_module.app.state, "product_core_runtime_factory"):
            del main_module.app.state.product_core_runtime_factory
        clear_settings_cache()
