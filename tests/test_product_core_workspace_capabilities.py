"""P2: workspace capabilities endpoint — capability-aware UI contract (§5).

The endpoint returns only the current Actor's booleans on a Person. Hidden or
missing Person, or a missing/revoked assignment, fails closed with 404
person_not_found; install admins without a Person assignment have no Person
surface; legacy family-access-v1 grants never gain condition/lab capability.
"""
from __future__ import annotations

import json
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
from tests.product_core_api_support import FixedClock, SequenceIds

SAME_ORIGIN = {"origin": "http://testserver"}

CAPABILITY_KEYS = frozenset(
    {
        "person_update",
        "source_write",
        "candidate_review",
        "medication_read",
        "medication_write",
        "condition_read",
        "condition_write",
        "lab_read",
        "lab_write",
        "timeline_read",
        "visit_read",
        "visit_write",
        "brief_read",
        "brief_write",
        "brief_export",
        "vault_export",
        "chat_use",
    }
)

ALL_TRUE = dict.fromkeys(sorted(CAPABILITY_KEYS), True)

CAREGIVER_READ_ONLY = {
    "person_update": False,
    "source_write": False,
    "candidate_review": False,
    "medication_read": True,
    "medication_write": False,
    "condition_read": True,
    "condition_write": False,
    "lab_read": True,
    "lab_write": False,
    "timeline_read": True,
    "visit_read": True,
    "visit_write": False,
    "brief_read": True,
    "brief_write": False,
    "brief_export": False,
    "vault_export": False,
    "chat_use": True,
}

V1_CAREGIVER_READ_ONLY = {
    "person_update": False,
    "source_write": False,
    "candidate_review": False,
    "medication_read": True,
    "medication_write": False,
    "condition_read": False,
    "condition_write": False,
    "lab_read": False,
    "lab_write": False,
    "timeline_read": True,
    "visit_read": True,
    "visit_write": False,
    "brief_read": True,
    "brief_write": False,
    "brief_export": False,
    "vault_export": False,
    "chat_use": True,
}


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
            carol_reviewer_invite = access.create_invitation(
                alice.actor_id,
                "alice-person",
                role="caregiver",
                optional_scopes={"candidate.review"},
                expires_at=clock() + timedelta(days=1),
                confirm_full_owner_access=False,
            )
            access.accept_invitation(
                carol.actor_id,
                carol_reviewer_invite.secret,
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


def _capabilities(harness: AccessHarness, person_id: str) -> dict[str, bool]:
    response = harness.client.get(
        f"/api/product-core/v1/people/{person_id}/workspace-capabilities"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload.keys()) == {"person_id", "capabilities"}
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, dict)
    assert set(capabilities.keys()) == CAPABILITY_KEYS
    return capabilities


def test_v2_owner_sees_all_capabilities_true(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("alice")
    response = access_harness.client.get(
        "/api/product-core/v1/people/alice-person/workspace-capabilities"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {"person_id": "alice-person", "capabilities": ALL_TRUE}


def test_read_only_caregiver_sees_base_reads_only(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("bob")
    capabilities = _capabilities(access_harness, "alice-person")
    assert capabilities == CAREGIVER_READ_ONLY


def test_caregiver_with_selected_optional_scope_sees_exactly_it(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("carol")
    capabilities = _capabilities(access_harness, "alice-person")
    assert capabilities == {
        **CAREGIVER_READ_ONLY,
        "candidate_review": True,
    }


def test_legacy_v1_grant_never_gains_condition_or_lab_capability(
    access_harness: AccessHarness,
) -> None:
    from app.config import get_settings
    from app.family_access.policy import CAREGIVER_BASE_SCOPES_V1
    from app.product_core.sqlite import SQLiteDatabase

    # Rewrite Bob's caregiver grant on alice-person to the frozen v1 scope set
    # (simulating a pre-P1 grant; scope_generation defaults to v1).
    settings = get_settings()
    database = SQLiteDatabase(settings.product_db_path)
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            UPDATE person_access_assignments
            SET scopes_json = ?
            WHERE actor_id = ? AND person_id = ? AND is_active = 1
            """,
            (
                json.dumps(sorted(CAREGIVER_BASE_SCOPES_V1), separators=(",", ":")),
                access_harness.actor_ids["bob"],
                "alice-person",
            ),
        )

    access_harness.login("bob")
    capabilities = _capabilities(access_harness, "alice-person")
    assert capabilities == V1_CAREGIVER_READ_ONLY


def test_install_admin_without_person_assignment_has_no_person_surface(
    access_harness: AccessHarness,
) -> None:
    access = main_module.app.state.family_access_runtime.service
    access.create_local_actor(
        access_harness.actor_ids["alice"],
        username="install-admin",
        display_name="Install admin",
        password="install-admin password value",
        installation_admin=True,
    )
    access_harness.login("install-admin")
    for person_id in ("alice-person", "bob-person", "missing-person"):
        response = access_harness.client.get(
            f"/api/product-core/v1/people/{person_id}/workspace-capabilities"
        )
        assert response.status_code == 404
        assert response.json() == {
            "error": {"code": "person_not_found", "message": "Person was not found."}
        }


def test_revoked_assignment_fails_closed_on_next_request(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("bob")
    assert _capabilities(access_harness, "alice-person") == CAREGIVER_READ_ONLY

    access = main_module.app.state.family_access_runtime.service
    access.revoke_assignment(
        access_harness.actor_ids["alice"],
        "alice-person",
        access_harness.actor_ids["bob"],
    )

    response = access_harness.client.get(
        "/api/product-core/v1/people/alice-person/workspace-capabilities"
    )
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "person_not_found", "message": "Person was not found."}
    }


def test_hidden_person_returns_standard_error_envelope(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("bob")
    response = access_harness.client.get(
        "/api/product-core/v1/people/carol-person/workspace-capabilities"
    )
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "person_not_found", "message": "Person was not found."}
    }


def test_response_shape_is_closed_with_exactly_seventeen_keys(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("alice")
    capabilities = _capabilities(access_harness, "alice-person")
    assert len(capabilities) == 17
    assert all(isinstance(value, bool) for value in capabilities.values())
