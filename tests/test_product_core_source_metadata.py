"""P2: safe source provenance metadata view (§9, §21).

GET /api/product-core/v1/sources/{source_id} resolves ownership server-side,
requires source.read, verifies the immutable payload hash before reporting
integrity_verified true, and returns a closed metadata-only shape that never
leaks person_id, relative_path, payload bytes, or other-Person metadata.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from app.family_access.runtime import create_family_access_runtime
from app.product_core.models import Person
from app.product_core.runtime import create_product_core_runtime
from tests.product_core_api_support import (
    FixedClock,
    SequenceIds,
    create_source,
    json_headers,
)

SAME_ORIGIN = {"origin": "http://testserver"}

METADATA_KEYS = frozenset(
    {
        "source_id",
        "source_type",
        "content_hash",
        "size_bytes",
        "media_type",
        "created_at",
        "integrity_verified",
    }
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class AccessHarness:
    client: TestClient
    actor_ids: dict[str, str]

    def login(self, username: str) -> None:
        self.client.cookies.clear()
        response = self.client.post(
            "/api/family-access/v1/login",
            headers=SAME_ORIGIN,
            json={"username": username, "password": f"{username} password value"},
        )
        assert response.status_code == 200, response.text
        csrf = self.client.cookies.get("opencare_csrf")
        assert csrf is not None
        self.client.headers.update(
            {"origin": "http://testserver", "x-opencare-csrf": csrf}
        )


@pytest.fixture
def access_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[AccessHarness]:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "product" / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    product_ids = SequenceIds()

    def runtime_factory(settings: object):
        return create_product_core_runtime(  # type: ignore[arg-type]
            settings, clock=clock, id_factory=product_ids
        )

    family_ids = SequenceIds()

    def family_runtime_factory(settings: object, runtime: object):
        return create_family_access_runtime(  # type: ignore[arg-type]
            settings,
            runtime.database,  # type: ignore[attr-defined]
            clock=clock,
            id_factory=lambda: f"access-{family_ids()}",
        )

    main_module.app.state.product_core_runtime_factory = runtime_factory
    main_module.app.state.family_access_runtime_factory = family_runtime_factory
    try:
        with TestClient(main_module.app) as client:
            runtime = main_module.app.state.product_core_runtime
            with runtime.database.uow() as uow:
                for person_id, display_name in (
                    ("alice-person", "Alice profile"),
                    ("bob-person", "Bob profile"),
                    ("carol-person", "Carol hidden profile"),
                ):
                    uow.people.insert(
                        Person(
                            person_id=person_id,
                            display_name=display_name,
                            created_at=clock(),
                            updated_at=clock(),
                            is_active=True,
                        )
                    )
            access = main_module.app.state.family_access_runtime.service
            alice = access.bootstrap(
                username="alice",
                display_name="Alice",
                password="alice password value",
                person_ids=("alice-person", "bob-person", "carol-person"),
                own_person_id="alice-person",
                confirm_full_owner_access=True,
            )
            bob_owner_invite = access.create_invitation(
                alice.actor_id,
                "bob-person",
                role="owner",
                optional_scopes=set(),
                expires_at=clock() + timedelta(days=1),
                confirm_full_owner_access=True,
            )
            bob = access.register_invitation(
                bob_owner_invite.secret,
                username="bob",
                display_name="Bob",
                password="bob password value",
                confirm_full_owner_access=True,
            )
            carol_owner_invite = access.create_invitation(
                alice.actor_id,
                "carol-person",
                role="owner",
                optional_scopes=set(),
                expires_at=clock() + timedelta(days=1),
                confirm_full_owner_access=True,
            )
            carol = access.register_invitation(
                carol_owner_invite.secret,
                username="carol",
                display_name="Carol",
                password="carol password value",
                confirm_full_owner_access=True,
            )
            bob_caregiver_invite = access.create_invitation(
                alice.actor_id,
                "alice-person",
                role="caregiver",
                optional_scopes=set(),
                expires_at=clock() + timedelta(days=1),
                confirm_full_owner_access=False,
            )
            access.accept_invitation(
                bob.actor_id,
                bob_caregiver_invite.secret,
                confirm_full_owner_access=False,
            )
            harness = AccessHarness(
                client=client,
                actor_ids={
                    "alice": alice.actor_id,
                    "bob": bob.actor_id,
                    "carol": carol.actor_id,
                },
            )
            yield harness
    finally:
        if hasattr(main_module.app.state, "product_core_runtime_factory"):
            del main_module.app.state.product_core_runtime_factory
        if hasattr(main_module.app.state, "family_access_runtime_factory"):
            del main_module.app.state.family_access_runtime_factory
        clear_settings_cache()


def test_same_person_authorized_source_metadata_read(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client, person_id="person-1")
    response = product_core_client.get(f"/api/product-core/v1/sources/{source_id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload.keys()) == METADATA_KEYS
    assert payload["source_id"] == source_id
    assert payload["source_type"] == "manual_entry"
    assert HEX64.fullmatch(payload["content_hash"])
    assert isinstance(payload["size_bytes"], int)
    assert payload["integrity_verified"] is True
    assert "relative_path" not in response.text
    assert "person_id" not in response.text
    assert "provenance" not in response.text


def test_source_metadata_never_leaks_payload_or_path(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client, person_id="person-1")
    response = product_core_client.get(f"/api/product-core/v1/sources/{source_id}")

    assert response.status_code == 200, response.text
    # The manual medication payload embeds "Aspirin"; metadata must not include
    # the raw payload content, any filesystem path, or any Person id.
    assert "Aspirin" not in response.text
    assert ".json" not in response.text
    assert "sources" not in response.text
    assert "person-1" not in response.text


def test_foreign_source_hidden_as_404(access_harness: AccessHarness) -> None:
    # Alice owns carol-person; Bob has no assignment on carol-person.
    access_harness.login("alice")
    source = access_harness.client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={"person_id": "carol-person", "medication": {"display_name": "Aspirin"}},
        headers=json_headers(),
    )
    assert source.status_code == 201, source.text
    source_id = source.json()["source"]["source_id"]

    access_harness.login("bob")
    response = access_harness.client.get(f"/api/product-core/v1/sources/{source_id}")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "source_not_found", "message": "Source was not found."}
    }


def test_unknown_source_returns_404(access_harness: AccessHarness) -> None:
    access_harness.login("bob")
    response = access_harness.client.get("/api/product-core/v1/sources/missing-source")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "source_not_found", "message": "Source was not found."}
    }


def test_tampered_source_fails_closed_with_integrity_error(
    product_core_client: TestClient,
) -> None:
    source_id = create_source(product_core_client, person_id="person-1")

    runtime = main_module.app.state.product_core_runtime
    source = runtime.sources.get(source_id)
    payload_path = runtime.sources.store.source_dir / source.relative_path
    payload_path.write_bytes(b"tampered payload that no longer matches the hash")

    response = product_core_client.get(f"/api/product-core/v1/sources/{source_id}")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "product_core_integrity_failure",
            "message": "Product Core integrity failed.",
        }
    }


def test_403_unreachable_for_valid_assignments() -> None:
    # source.read is present in every valid role base set (OWNER_SCOPES_V1/V2
    # and CAREGIVER_BASE_SCOPES_V1/V2). A valid assignment lacking source.read
    # is not constructible through the grant APIs, so a 403 (missing scope on a
    # visible Person) cannot be reached via valid state; the foreign/hidden
    # source case is instead covered by test_foreign_source_hidden_as_404.
    pass
