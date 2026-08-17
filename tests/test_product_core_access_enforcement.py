from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import clear_settings_cache
from app.family_access.runtime import create_family_access_runtime
from app.product_core.models import Person
from app.product_core.runtime import create_product_core_runtime
from tests.product_core_api_support import FixedClock, SequenceIds, json_headers

SAME_ORIGIN = {"origin": "http://testserver"}


def _sql_shape(statement: str) -> str:
    without_strings = re.sub(r"'(?:''|[^'])*'", "?", statement)
    without_nulls = re.sub(r"\bnull\b", "?", without_strings, flags=re.IGNORECASE)
    without_literals = re.sub(r"\b\d+\b", "?", without_nulls)
    return " ".join(without_literals.casefold().split())


@dataclass
class AccessHarness:
    client: TestClient
    actor_ids: dict[str, str]
    invitation_secret: str

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

    def select(self, person_id: str) -> None:
        response = self.client.put(
            "/api/family-access/v1/active-person",
            json={"person_id": person_id},
        )
        assert response.status_code == 204, response.text


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
            family = access.create_family(alice.actor_id, "Selected family")
            for person_id in ("alice-person", "bob-person", "carol-person"):
                access.add_membership(alice.actor_id, family.family_id, person_id)
            access.create_relationship(
                alice.actor_id,
                family.family_id,
                person_id="alice-person",
                related_person_id="bob-person",
                relationship_type="sibling",
            )
            excluded_invite = access.create_invitation(
                alice.actor_id,
                "alice-person",
                role="caregiver",
                optional_scopes={"vault.export"},
                expires_at=clock() + timedelta(days=1),
                confirm_full_owner_access=False,
            )
            harness = AccessHarness(
                client=client,
                actor_ids={
                    "alice": alice.actor_id,
                    "bob": bob.actor_id,
                    "carol": carol.actor_id,
                },
                invitation_secret=excluded_invite.secret,
            )
            yield harness
    finally:
        if hasattr(main_module.app.state, "product_core_runtime_factory"):
            del main_module.app.state.product_core_runtime_factory
        if hasattr(main_module.app.state, "family_access_runtime_factory"):
            del main_module.app.state.family_access_runtime_factory
        clear_settings_cache()


def test_product_core_requires_actor_session_and_exact_csrf(
    access_harness: AccessHarness,
) -> None:
    client = access_harness.client
    client.cookies.clear()

    unauthenticated = client.get("/api/product-core/v1/people")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {
        "error": {"code": "authentication_required", "message": "Authentication required."}
    }

    access_harness.login("bob")
    invalid_csrf = client.patch(
        "/api/product-core/v1/people/bob-person",
        headers={"origin": "http://testserver", "x-opencare-csrf": "invalid"},
        json={"display_name": "Should not change"},
    )

    assert invalid_csrf.status_code == 403
    assert invalid_csrf.json() == {
        "error": {"code": "csrf_rejected", "message": "CSRF validation failed."}
    }


def test_hidden_and_missing_resource_checks_use_the_same_query_shape(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_harness.login("bob")
    database = main_module.app.state.product_core_runtime.database
    original_connect = database.connect
    statements: list[str] = []

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(database, "connect", traced_connect)
    hidden = access_harness.client.get("/api/product-core/v1/people/carol-person")
    hidden_shape = [_sql_shape(statement) for statement in statements]
    statements.clear()
    missing = access_harness.client.get("/api/product-core/v1/people/missing-person")
    missing_shape = [_sql_shape(statement) for statement in statements]

    assert hidden.status_code == missing.status_code == 404
    assert hidden_shape == missing_shape


def test_mutation_authorization_and_write_share_one_database_transaction(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_harness.login("bob")
    database = main_module.app.state.product_core_runtime.database
    original_connect = database.connect
    statements_by_connection: dict[int, list[str]] = {}
    next_connection_id = 0

    def traced_connect():
        nonlocal next_connection_id
        connection = original_connect()
        connection_id = next_connection_id
        next_connection_id += 1
        statements_by_connection[connection_id] = []
        connection.set_trace_callback(
            lambda statement: statements_by_connection[connection_id].append(
                _sql_shape(statement)
            )
        )
        return connection

    monkeypatch.setattr(database, "connect", traced_connect)
    response = access_harness.client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "bob-person", "content": "one transaction"},
    )

    assert response.status_code == 201, response.text
    authorization_connections = {
        connection_id
        for connection_id, statements in statements_by_connection.items()
        if any("from person_access_assignments as paa" in item for item in statements)
    }
    write_connections = {
        connection_id
        for connection_id, statements in statements_by_connection.items()
        if any(item.startswith("insert into sources") for item in statements)
    }
    assert len(write_connections) == 1
    assert write_connections <= authorization_connections


def test_audit_failures_roll_back_mutations_and_preserve_denials(
    access_harness: AccessHarness,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    access_harness.login("bob")
    client = access_harness.client
    database = main_module.app.state.product_core_runtime.database
    family_service = main_module.app.state.family_access_runtime.service

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise OSError("forced audit persistence failure")

    monkeypatch.setattr(family_service, "audit_writer", fail_audit)
    mutation = client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "bob-person", "content": "must roll back"},
    )
    hidden = client.get("/api/product-core/v1/people/carol-person")
    forbidden = client.post(
        "/api/product-core/v1/sources/plain-text",
        json={"person_id": "alice-person", "content": "must stay denied"},
    )

    assert mutation.status_code == 503
    assert hidden.status_code == 404
    assert forbidden.status_code == 403
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sources WHERE person_id IN (?, ?)",
            ("bob-person", "alice-person"),
        ).fetchone()[0] == 0
    assert "product_core_denial_audit_failed" in caplog.text
    assert "carol-person" not in caplog.text
    assert "alice-person" not in caplog.text


def test_people_list_and_person_errors_do_not_disclose_hidden_people(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("bob")
    client = access_harness.client

    listed = client.get("/api/product-core/v1/people")
    hidden = client.get("/api/product-core/v1/people/carol-person")
    missing = client.get("/api/product-core/v1/people/missing-person")
    insufficient = client.patch(
        "/api/product-core/v1/people/alice-person",
        json={"display_name": "Forbidden update"},
    )

    assert listed.status_code == 200
    assert [
        (person["person_id"], person["display_name"])
        for person in listed.json()["people"]
    ] == [
        ("alice-person", "Alice profile"),
        ("bob-person", "Bob profile"),
    ]
    assert "count" not in listed.text.lower()
    assert "carol" not in listed.text.lower()
    assert hidden.status_code == missing.status_code == 404
    assert hidden.content == missing.content
    assert hidden.headers["content-type"] == missing.headers["content-type"]
    assert insufficient.status_code == 403
    assert insufficient.json() == {
        "error": {"code": "scope_forbidden", "message": "Required scope is not granted."}
    }


def test_person_create_requires_literal_owner_confirmation_and_is_atomic(
    access_harness: AccessHarness,
) -> None:
    access_harness.login("bob")
    client = access_harness.client
    database = main_module.app.state.product_core_runtime.database

    rejected = client.post(
        "/api/product-core/v1/people",
        json={"display_name": "Unowned", "confirm_owner_assignment": False},
    )
    coerced = client.post(
        "/api/product-core/v1/people",
        json={"display_name": "Coerced", "confirm_owner_assignment": "true"},
    )

    assert rejected.status_code == 403
    assert coerced.status_code == 422
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM people WHERE display_name IN ('Unowned', 'Coerced')"
        ).fetchone()[0] == 0

    created = client.post(
        "/api/product-core/v1/people",
        json={"display_name": "Owned child", "confirm_owner_assignment": True},
    )

    assert created.status_code == 201
    person_id = created.json()["person_id"]
    with database.connect() as connection:
        assignment = connection.execute(
            "SELECT role, is_active FROM person_access_assignments "
            "WHERE actor_id = ? AND person_id = ?",
            (access_harness.actor_ids["bob"], person_id),
        ).fetchone()
        assert tuple(assignment) == ("owner", 1)


def test_nested_resource_ownership_and_scope_map(
    access_harness: AccessHarness,
) -> None:
    client = access_harness.client
    access_harness.login("alice")
    source = client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": "alice-person",
            "medication": {"display_name": "Alice medicine"},
        },
    )
    assert source.status_code == 201, source.text
    source_id = source.json()["source"]["source_id"]
    candidate = client.post(
        "/api/product-core/v1/candidates/medications",
        json={
            "person_id": "alice-person",
            "source_id": source_id,
            "display_name": "Alice medicine",
        },
    )
    assert candidate.status_code == 201, candidate.text
    candidate_id = candidate.json()["id"]
    visit = client.post(
        "/api/product-core/v1/visits",
        json={"person_id": "alice-person", "title": "Alice visit"},
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["visit_id"]
    question = client.post(
        f"/api/product-core/v1/visits/{visit_id}/questions",
        json={"question_text": "Alice private question"},
    )
    assert question.status_code == 201, question.text
    question_id = question.json()["question_id"]

    access_harness.login("carol")
    carol_visit = client.post(
        "/api/product-core/v1/visits",
        json={"person_id": "carol-person", "title": "Carol hidden visit"},
    )
    assert carol_visit.status_code == 201, carol_visit.text
    carol_visit_id = carol_visit.json()["visit_id"]
    carol_question = client.post(
        f"/api/product-core/v1/visits/{carol_visit_id}/questions",
        json={"question_text": "Carol hidden question"},
    )
    assert carol_question.status_code == 201, carol_question.text
    carol_question_id = carol_question.json()["question_id"]
    review_without_medication_write = client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm", json={}
    )
    assert review_without_medication_write.status_code == 403

    access_harness.login("bob")
    assert client.get(f"/api/product-core/v1/candidates/{candidate_id}").status_code == 200
    assert client.get("/api/product-core/v1/people/alice-person/candidates").status_code == 200
    assert client.get("/api/product-core/v1/people/alice-person/medications").status_code == 200
    assert client.get("/api/product-core/v1/people/alice-person/timeline").status_code == 200
    assert client.get(f"/api/product-core/v1/visits/{visit_id}").status_code == 200
    assert client.get(f"/api/product-core/v1/visits/{visit_id}/questions").status_code == 200
    assert (
        client.post(
            "/api/product-core/v1/sources/plain-text",
            json={"person_id": "alice-person", "content": "forbidden"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/product-core/v1/candidates/{candidate_id}/reject", json={}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/product-core/v1/visits",
            json={"person_id": "alice-person", "title": "Forbidden"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/product-core/v1/visit-questions/{question_id}",
            json={"question_text": "Forbidden"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/product-core/v1/visits/{visit_id}/brief", json={}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/product-core/v1/people/alice-person/visit-briefs:generate",
            json={"visit_title": "Forbidden brief", "selected_record_ids": []},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/product-core/v1/people/alice-person/vault-export", json={}
        ).status_code
        == 403
    )

    hidden_visit = client.get(f"/api/product-core/v1/visits/{carol_visit_id}")
    missing_visit = client.get("/api/product-core/v1/visits/missing-visit")
    hidden_question = client.patch(
        f"/api/product-core/v1/visit-questions/{carol_question_id}",
        json={"question_text": "Guess"},
    )
    missing_question = client.patch(
        "/api/product-core/v1/visit-questions/missing-question",
        json={"question_text": "Guess"},
    )
    assert hidden_visit.status_code == missing_visit.status_code == 404
    assert hidden_visit.content == missing_visit.content
    assert hidden_question.status_code == missing_question.status_code == 404
    assert hidden_question.content == missing_question.content


def test_portable_export_v2_is_scoped_deterministic_and_audited(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_harness.login("alice")
    client = access_harness.client

    first = client.post(
        "/api/product-core/v1/people/alice-person/vault-export", json={}
    )
    second = client.post(
        "/api/product-core/v1/people/alice-person/vault-export", json={}
    )

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert first.headers["content-disposition"] == (
        'attachment; filename="opencare-person-vault-v2.zip"'
    )
    with zipfile.ZipFile(BytesIO(first.content)) as archive:
        manifest_bytes = archive.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        vault = json.loads(archive.read("vault.json"))
        assert archive.read("manifest.sha256") == hashlib.sha256(manifest_bytes).hexdigest().encode(
            "ascii"
        )
    assert manifest["format_version"] == 3
    assert manifest["product_core_schema_version"] == 7
    assert vault["format_version"] == 3
    assert len(vault["family_memberships"]) == 1
    assert vault["family_memberships"][0]["person_id"] == "alice-person"
    assert len(vault["person_relationships"]) == 1
    assert vault["person_access_consent_history"]
    assert vault["person_access_assignments"]
    assert {actor["actor_id"] for actor in vault["actors"]} == {
        access_harness.actor_ids["alice"],
        access_harness.actor_ids["bob"],
        access_harness.actor_ids["carol"],
    }
    serialized = first.content.decode("latin-1")
    for forbidden in (
        "actor_credentials",
        "installation_admin_assignments",
        "own_person_links",
        "access_invitations",
        "access_audit_events",
        "secret_hash",
        access_harness.invitation_secret,
        "alice password value",
    ):
        assert forbidden not in serialized

    database = main_module.app.state.product_core_runtime.database
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM access_audit_events "
            "WHERE actor_id = ? AND action_code = 'vault.export' "
            "AND target_id = 'alice-person' AND outcome = 'success'",
            (access_harness.actor_ids["alice"],),
        ).fetchone()[0] == 2

    family_service = main_module.app.state.family_access_runtime.service

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise OSError("forced audit failure")

    monkeypatch.setattr(family_service, "audit_writer", fail_audit)
    failed = client.post(
        "/api/product-core/v1/people/alice-person/vault-export", json={}
    )
    assert failed.status_code == 503
    assert failed.headers["content-type"].startswith("application/json")
    assert failed.json() == {
        "error": {
            "code": "access_audit_unavailable",
            "message": "Sensitive access could not be audited.",
        }
    }


def test_live_pages_require_session_and_revalidate_active_person(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = access_harness.client
    client.cookies.clear()
    for path in ("/workspace", "/vault", "/chat"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 401

    access_harness.login("bob")
    assert client.get("/workspace").status_code == 200
    assert client.get("/vault").status_code == 404
    assert client.get("/chat").status_code == 404

    def demo_fallback_forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("live routes must not load demo/local-file vault context")

    monkeypatch.setattr(main_module, "load_active_vault", demo_fallback_forbidden)
    access_harness.select("alice-person")
    vault = client.get("/vault")
    chat = client.get("/chat")
    assert vault.status_code == chat.status_code == 200
    assert "Alice profile" in vault.text
    assert "Carol hidden profile" not in vault.text
    assert "Alice profile" in chat.text

    family_service = main_module.app.state.family_access_runtime.service
    family_service.revoke_assignment(
        access_harness.actor_ids["alice"],
        "alice-person",
        access_harness.actor_ids["bob"],
    )
    for path in ("/workspace", "/vault", "/chat"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 404
        assert "demo" not in response.text.lower()


def test_legacy_chat_requires_consent_gate(access_harness: AccessHarness) -> None:
    access_harness.login("bob")
    access_harness.select("bob-person")
    response = access_harness.client.post(
        "/api/chat", json={"question": "Which medications are recorded?"}
    )
    assert response.status_code == 410
    assert response.json()["code"] == "consent_required"


def test_legacy_chat_gate_does_not_call_provider(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_harness.login("bob")
    access_harness.select("bob-person")
    provider_calls = 0

    def forbidden_service(*_args: object, **_kwargs: object) -> object:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("legacy chat must not invoke provider")

    monkeypatch.setattr(
        main_module.GuardedChatService,
        "for_context",
        classmethod(forbidden_service),
        raising=False,
    )
    response = access_harness.client.post("/api/chat", json={"question": "What is recorded?"})
    assert response.status_code == 410
    assert provider_calls == 0


def test_brief_export_requires_scope_and_durable_access_audit(
    access_harness: AccessHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    access_harness.login("alice")
    client = access_harness.client
    visit = client.post(
        "/api/product-core/v1/visits",
        json={"person_id": "alice-person", "title": "Export visit"},
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["visit_id"]
    initialized = client.post(f"/api/product-core/v1/visits/{visit_id}/brief", json={})
    assert initialized.status_code == 201, initialized.text
    generated = client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/revisions:generate",
        json={"selected_record_ids": [], "expected_current_revision_number": None},
    )
    assert generated.status_code == 201, generated.text

    exported = client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/current:export", json={}
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")

    family_service = main_module.app.state.family_access_runtime.service

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise OSError("forced brief audit failure")

    monkeypatch.setattr(family_service, "audit_writer", fail_audit)
    failed = client.post(
        f"/api/product-core/v1/visits/{visit_id}/brief/current:export", json={}
    )
    assert failed.status_code == 503
    assert failed.headers["content-type"].startswith("application/json")
    assert "#" not in failed.text


def test_wrong_person_condition_scopes_deny_and_hide_without_silent_expansion(
    access_harness: AccessHarness,
) -> None:
    """Bob (caregiver) with a legacy family-access-v1 grant must never read
    Alice's conditions: visible Person -> 403, hidden Person -> 404, guessed
    record/candidate IDs -> 403 (visible person, missing scope)."""
    import json as _json

    from app.family_access.policy import CAREGIVER_BASE_SCOPES_V1

    client = access_harness.client
    access_harness.login("alice")
    source = client.post(
        "/api/product-core/v1/sources/manual-condition",
        json={"person_id": "alice-person", "condition": {"display_name": "Asthma"}},
        headers=json_headers(),
    )
    assert source.status_code == 201, source.text
    candidate = client.post(
        "/api/product-core/v1/candidates/conditions",
        json={
            "person_id": "alice-person",
            "source_id": source.json()["source"]["source_id"],
            "display_name": "Asthma",
        },
        headers=json_headers(),
    )
    assert candidate.status_code == 201, candidate.text
    record = client.post(
        f"/api/product-core/v1/candidates/{candidate.json()['id']}/confirm",
        json={},
        headers=json_headers(),
    )
    assert record.status_code == 200, record.text
    record_id = record.json()["id"]
    candidate_id = candidate.json()["id"]

    # Rewrite Bob's caregiver grant on alice-person to the frozen v1 scope set
    # (simulating a pre-P1 grant; scope_generation defaults to v1).
    from app.product_core.sqlite import SQLiteDatabase
    from app.config import get_settings

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
                _json.dumps(sorted(CAREGIVER_BASE_SCOPES_V1), separators=(",", ":")),
                access_harness.actor_ids["bob"],
                "alice-person",
            ),
        )

    access_harness.login("bob")
    visible = client.get("/api/product-core/v1/people/alice-person/conditions")
    hidden = client.get("/api/product-core/v1/people/carol-person/conditions")
    missing = client.get("/api/product-core/v1/people/missing-person/conditions")
    hidden_record = client.get(f"/api/product-core/v1/conditions/{record_id}")
    missing_record = client.get("/api/product-core/v1/conditions/missing-record")
    hidden_candidate = client.get(
        f"/api/product-core/v1/candidates/conditions/{candidate_id}"
    )
    missing_candidate = client.get(
        "/api/product-core/v1/candidates/conditions/missing-candidate"
    )
    list_candidates = client.get(
        "/api/product-core/v1/people/alice-person/condition-candidates"
    )

    assert visible.status_code == 403
    assert hidden.status_code == missing.status_code == 404
    assert hidden.content == missing.content
    # Alice's real record/candidate are visible-person resources Bob lacks the
    # condition scope for -> 403; nonexistent IDs are 404.
    assert hidden_record.status_code == 403
    assert missing_record.status_code == 404
    assert hidden_candidate.status_code == 403
    assert missing_candidate.status_code == 404
    assert list_candidates.status_code == 403


def test_condition_review_requires_candidate_review_and_condition_write(
    access_harness: AccessHarness,
) -> None:
    """Carol has candidate.review but NOT condition.write: confirming a
    condition candidate is denied. Bob (v2 base) lacks candidate.review and is
    likewise denied. No client-supplied Person ID grants authority."""
    client = access_harness.client
    access_harness.login("alice")
    source = client.post(
        "/api/product-core/v1/sources/manual-condition",
        json={"person_id": "alice-person", "condition": {"display_name": "Eczema"}},
        headers=json_headers(),
    )
    candidate = client.post(
        "/api/product-core/v1/candidates/conditions",
        json={
            "person_id": "alice-person",
            "source_id": source.json()["source"]["source_id"],
            "display_name": "Eczema",
        },
        headers=json_headers(),
    )
    candidate_id = candidate.json()["id"]

    access_harness.login("carol")
    carol_confirm = client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    assert carol_confirm.status_code == 403
    access_harness.login("bob")
    bob_confirm = client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    assert bob_confirm.status_code == 403

    # The owner (v2 full scope set) can confirm.
    access_harness.login("alice")
    confirmed = client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/confirm",
        json={},
        headers=json_headers(),
    )
    assert confirmed.status_code == 200
    # Bob can now LIST conditions under the v2 caregiver base (condition.read).
    access_harness.login("bob")
    listed = client.get("/api/product-core/v1/people/alice-person/conditions")
    assert listed.status_code == 200
    assert listed.json()["conditions"][0]["display_name"] == "Eczema"
