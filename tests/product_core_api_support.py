from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from app.product_core.runtime import create_product_core_runtime


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self) -> None:
        self.number = 0

    def __call__(self) -> str:
        self.number += 1
        return f"api-id-{self.number}"


def json_headers() -> dict[str, str]:
    return {
        "content-type": "application/json; charset=utf-8",
        "origin": "http://testserver",
    }


@pytest.fixture
def product_core_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "sources"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()
    clock = FixedClock(datetime(2026, 7, 26, 12, tzinfo=UTC))
    ids = SequenceIds()
    def runtime_factory(settings: object):
        return create_product_core_runtime(settings, clock=clock, id_factory=ids)  # type: ignore[arg-type]

    main_module.app.state.product_core_runtime_factory = runtime_factory
    try:
        with TestClient(main_module.app) as client:
            yield client
    finally:
        if hasattr(main_module.app.state, "product_core_runtime_factory"):
            del main_module.app.state.product_core_runtime_factory
        clear_settings_cache()


def create_source(client: TestClient, person_id: str = "person-1") -> str:
    response = client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": person_id,
            "medication": {"display_name": "Aspirin"},
        },
        headers=json_headers(),
    )
    assert response.status_code == 201
    return response.json()["source"]["source_id"]


def create_candidate(
    client: TestClient,
    source_id: str,
    *,
    person_id: str = "person-1",
    display_name: str = "Aspirin",
) -> str:
    response = client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": person_id,
            "source_id": source_id,
            "display_name": display_name,
        },
        headers=json_headers(),
    )
    assert response.status_code == 201
    return response.json()["id"]
