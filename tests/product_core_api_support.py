from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from app.family_access.runtime import create_family_access_runtime
from app.product_core.models import Person
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
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "product" / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()
    clock = FixedClock(datetime(2026, 7, 26, 12, tzinfo=UTC))
    ids = SequenceIds()
    def runtime_factory(settings: object):
        return create_product_core_runtime(settings, clock=clock, id_factory=ids)  # type: ignore[arg-type]

    family_ids = SequenceIds()

    def family_runtime_factory(settings: object, runtime: object):
        return create_family_access_runtime(  # type: ignore[arg-type]
            settings,
            runtime.database,  # type: ignore[attr-defined]
            clock=clock,
            id_factory=lambda: f"family-{family_ids()}",
        )

    main_module.app.state.product_core_runtime_factory = runtime_factory
    main_module.app.state.family_access_runtime_factory = family_runtime_factory
    try:
        with TestClient(main_module.app) as client:
            runtime = main_module.app.state.product_core_runtime
            now = clock()
            with runtime.database.uow() as uow:
                for person_id in ("person-1", "person-2"):
                    uow.people.insert(
                        Person(
                            person_id=person_id,
                            display_name=f"Profile {person_id}",
                            created_at=now,
                            updated_at=now,
                            is_active=True,
                        )
                    )
            bootstrap = client.post(
                "/api/family-access/v1/bootstrap",
                headers={"origin": "http://testserver"},
                json={
                    "username": "legacy-owner",
                    "display_name": "Legacy owner",
                    "password": "correct horse battery",
                    "person_ids": ["person-1", "person-2"],
                    "confirm_full_owner_access": True,
                },
            )
            assert bootstrap.status_code == 201, bootstrap.text
            csrf = client.cookies.get("opencare_csrf")
            assert csrf is not None
            client.headers.update(
                {"origin": "http://testserver", "x-opencare-csrf": csrf}
            )
            yield client
    finally:
        if hasattr(main_module.app.state, "product_core_runtime_factory"):
            del main_module.app.state.product_core_runtime_factory
        if hasattr(main_module.app.state, "family_access_runtime_factory"):
            del main_module.app.state.family_access_runtime_factory
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
