import sqlite3
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import app.main as main_module
from app.config import clear_settings_cache
from app.family_access.api import router as family_access_router
from app.family_access.policy import OWNER_SCOPES
from app.product_core.models import Person

SAME_ORIGIN = {"origin": "http://testserver"}


def _configure_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: str = "development",
) -> None:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "product" / "sources"))
    monkeypatch.setenv(
        "OPENCARE_SESSION_DB_PATH", str((tmp_path / "runtime" / "sessions.sqlite3").resolve())
    )
    monkeypatch.setenv("OPENCARE_ENV", environment)
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    if environment == "production":
        monkeypatch.setenv("OPENCARE_SECRET_KEY", "s" * 32)
    clear_settings_cache()


@pytest.fixture
def family_access_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _configure_environment(tmp_path, monkeypatch)
    try:
        with TestClient(main_module.app) as client:
            runtime = main_module.app.state.product_core_runtime
            now = runtime.clock()
            with runtime.database.uow() as uow:
                uow.people.insert(
                    Person(
                        person_id="existing-person",
                        display_name="Existing profile",
                        created_at=now,
                        updated_at=now,
                        is_active=True,
                    )
                )
            yield client
    finally:
        clear_settings_cache()


def _bootstrap(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/family-access/v1/bootstrap",
        headers=SAME_ORIGIN,
        json={
            "username": "owner",
            "display_name": "Local owner",
            "password": "correct horse battery",
            "person_ids": ["existing-person"],
            "own_person_id": "existing-person",
            "confirm_full_owner_access": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    csrf = client.cookies.get("opencare_csrf")
    assert csrf is not None
    return {**SAME_ORIGIN, "x-opencare-csrf": csrf}


def _assert_session_cookies_are_secure(response: object) -> None:
    headers = response.headers.get_list("set-cookie")  # type: ignore[attr-defined]
    session_headers = [
        header
        for header in headers
        if header.startswith("opencare_session=") or header.startswith("opencare_csrf=")
    ]
    assert len(session_headers) == 2
    assert all("Secure" in header.split("; ") for header in session_headers)


def _assert_current_session_uses_active_credential(client: TestClient) -> None:
    runtime = main_module.app.state.family_access_runtime
    token = client.cookies.get("opencare_session")
    assert token is not None
    record = runtime.sessions.resolve(token)
    assert record is not None
    with runtime.service.database.connect() as connection:
        active_credential_id = connection.execute(
            "SELECT credential_id FROM actor_credentials "
            "WHERE actor_id = ? AND revoked_at IS NULL",
            (record.actor_id,),
        ).fetchone()[0]
    assert record.credential_id == active_credential_id


def test_bootstrap_login_logout_and_csrf_contract(family_access_client: TestClient) -> None:
    client = family_access_client
    status = client.get("/api/family-access/v1/bootstrap-status")
    assert status.status_code == 200
    assert status.json() == {"bootstrap_available": True}

    missing_origin = client.post(
        "/api/family-access/v1/bootstrap",
        json={
            "username": "owner",
            "display_name": "Local owner",
            "password": "correct horse battery",
            "person_ids": ["existing-person"],
            "confirm_full_owner_access": True,
        },
    )
    assert missing_origin.status_code == 403
    assert client.get("/api/family-access/v1/bootstrap-status").json() == {
        "bootstrap_available": True
    }

    coerced_confirmation = client.post(
        "/api/family-access/v1/bootstrap",
        headers=SAME_ORIGIN,
        json={
            "username": "owner",
            "display_name": "Local owner",
            "password": "correct horse battery",
            "person_ids": ["existing-person"],
            "confirm_full_owner_access": "true",
        },
    )
    assert coerced_confirmation.status_code == 422
    assert client.get("/api/family-access/v1/bootstrap-status").json() == {
        "bootstrap_available": True
    }

    payload = _bootstrap(client)
    assert payload["installation_admin"] is True
    assert payload["owner_assignment_count"] == 1
    assert payload["owner_assignments"] == [
        {
            "person_id": "existing-person",
            "role": "owner",
            "scopes": sorted(OWNER_SCOPES),
        }
    ]
    session_cookie = client.cookies.get("opencare_session")
    csrf_cookie = client.cookies.get("opencare_csrf")
    assert session_cookie and csrf_cookie
    session_header = next(item for item in client.cookies.jar if item.name == "opencare_session")
    assert session_header.has_nonstandard_attr("HttpOnly")
    assert session_header.get_nonstandard_attr("SameSite") == "lax"

    me = client.get("/api/family-access/v1/me")
    assert me.status_code == 200
    assert me.json()["actor"]["username"] == "owner"
    assert me.json()["active_person_id"] is None

    missing_csrf = client.post(
        "/api/family-access/v1/people",
        headers=SAME_ORIGIN,
        json={
            "display_name": "Child",
            "confirm_owner_assignment": True,
        },
    )
    assert missing_csrf.status_code == 403

    created = client.post(
        "/api/family-access/v1/people",
        headers=_csrf_headers(client),
        json={
            "display_name": "Child",
            "confirm_owner_assignment": True,
        },
    )
    assert created.status_code == 201

    logout = client.post("/api/family-access/v1/logout", headers=_csrf_headers(client), json={})
    assert logout.status_code == 204
    assert client.get("/api/family-access/v1/me").status_code == 401

    cross_origin = client.post(
        "/api/family-access/v1/login",
        headers={"origin": "https://attacker.example"},
        json={"username": "owner", "password": "correct horse battery"},
    )
    assert cross_origin.status_code == 403
    invalid = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "unknown", "password": "wrong password value"},
    )
    assert invalid.status_code == 401
    login = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "OWNER", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    assert client.get("/api/family-access/v1/me").status_code == 200


def test_https_development_secures_bootstrap_login_and_registration_cookies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(tmp_path, monkeypatch)
    try:
        with TestClient(main_module.app, base_url="https://testserver") as client:
            origin = {"origin": "https://testserver"}
            bootstrap = client.post(
                "/api/family-access/v1/bootstrap",
                headers=origin,
                json={
                    "username": "owner",
                    "display_name": "Owner",
                    "password": "correct horse battery",
                },
            )
            assert bootstrap.status_code == 201, bootstrap.text
            _assert_session_cookies_are_secure(bootstrap)
            _assert_current_session_uses_active_credential(client)

            login = client.post(
                "/api/family-access/v1/login",
                headers=origin,
                json={"username": "owner", "password": "correct horse battery"},
            )
            assert login.status_code == 200, login.text
            _assert_session_cookies_are_secure(login)
            _assert_current_session_uses_active_credential(client)

            runtime = main_module.app.state.family_access_runtime
            owner_id = bootstrap.json()["actor"]["actor_id"]
            person_id = runtime.service.create_person(
                owner_id,
                display_name="Invite target",
                date_of_birth=None,
                confirm_owner_assignment=True,
            )
            invitation = runtime.service.create_invitation(
                owner_id,
                person_id,
                role="caregiver",
                optional_scopes=set(),
                expires_at=main_module.app.state.product_core_runtime.clock()
                + timedelta(days=1),
                confirm_full_owner_access=False,
            )
            registration = client.post(
                "/api/family-access/v1/invite/register",
                headers=origin,
                json={
                    "secret": invitation.secret,
                    "username": "caregiver",
                    "display_name": "Caregiver",
                    "password": "caregiver password value",
                    "confirm_full_owner_access": False,
                },
            )
            assert registration.status_code == 201, registration.text
            _assert_session_cookies_are_secure(registration)
            _assert_current_session_uses_active_credential(client)
    finally:
        clear_settings_cache()


def test_trusted_forwarded_https_secures_development_session_cookies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(tmp_path, monkeypatch)
    proxy_app = ProxyHeadersMiddleware(main_module.app, trusted_hosts="*")
    try:
        with TestClient(proxy_app) as client:
            response = client.post(
                "/api/family-access/v1/bootstrap",
                headers={
                    "origin": "https://testserver",
                    "x-forwarded-proto": "https",
                },
                json={
                    "username": "owner",
                    "display_name": "Owner",
                    "password": "correct horse battery",
                },
            )
            assert response.status_code == 201, response.text
            _assert_session_cookies_are_secure(response)
    finally:
        clear_settings_cache()


def test_production_policy_secures_session_cookies_over_http_test_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(tmp_path, monkeypatch, environment="production")
    try:
        with TestClient(main_module.app) as client:
            response = client.post(
                "/api/family-access/v1/bootstrap",
                headers=SAME_ORIGIN,
                json={
                    "username": "owner",
                    "display_name": "Owner",
                    "password": "correct horse battery",
                },
            )
            assert response.status_code == 201, response.text
            _assert_session_cookies_are_secure(response)
    finally:
        clear_settings_cache()


def test_family_access_route_contract_and_body_only_invitation_paths(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    expected = {
        ("GET", "/api/family-access/v1/bootstrap-status"),
        ("POST", "/api/family-access/v1/bootstrap"),
        ("POST", "/api/family-access/v1/login"),
        ("POST", "/api/family-access/v1/logout"),
        ("GET", "/api/family-access/v1/me"),
        ("POST", "/api/family-access/v1/password:change"),
        ("PUT", "/api/family-access/v1/active-person"),
        ("GET", "/api/family-access/v1/actors"),
        ("POST", "/api/family-access/v1/actors/{actor_id}:deactivate"),
        ("POST", "/api/family-access/v1/people"),
        ("GET", "/api/family-access/v1/families"),
        ("POST", "/api/family-access/v1/families"),
        ("GET", "/api/family-access/v1/families/{family_id}"),
        ("POST", "/api/family-access/v1/families/{family_id}:archive"),
        ("POST", "/api/family-access/v1/families/{family_id}/memberships"),
        ("POST", "/api/family-access/v1/families/{family_id}/relationships"),
        ("GET", "/api/family-access/v1/people/{person_id}/access-assignments"),
        ("POST", "/api/family-access/v1/people/{person_id}/access-assignments"),
        ("GET", "/api/family-access/v1/people/{person_id}/consents"),
        ("GET", "/api/family-access/v1/people/{person_id}/access-audit"),
        ("POST", "/api/family-access/v1/people/{person_id}/invitations"),
        ("POST", "/api/family-access/v1/invite/preview"),
        ("POST", "/api/family-access/v1/invite/register"),
        ("POST", "/api/family-access/v1/invite/accept"),
    }
    routes = {
        (method, route.path)
        for route in family_access_router.routes
        for method in (getattr(route, "methods", None) or set())
    }
    assert expected <= routes
    assert all("secret" not in path and "token" not in path for _, path in expected)

    _bootstrap(client)
    invitation = client.post(
        "/api/family-access/v1/people/existing-person/invitations",
        headers=_csrf_headers(client),
        json={
            "role": "caregiver",
            "optional_scopes": ["vault.export"],
            "expires_at": "2027-08-02T10:00:00+00:00",
            "confirm_full_owner_access": False,
        },
    )
    assert invitation.status_code == 201, invitation.text
    secret = invitation.json()["secret"]
    assert secret not in invitation.request.url.path
    assert secret not in str(invitation.request.url.query)

    preview = client.post(
        "/api/family-access/v1/invite/preview",
        headers=SAME_ORIGIN,
        json={"secret": secret},
    )
    assert preview.status_code == 200
    assert preview.json()["role"] == "caregiver"
    generic_invalid = client.post(
        "/api/family-access/v1/invite/preview",
        headers=SAME_ORIGIN,
        json={"secret": "invalid invitation secret"},
    )
    assert generic_invalid.status_code == 404
    assert generic_invalid.json() == {
        "error": {
            "code": "invitation_unavailable",
            "message": "Invitation is unavailable.",
        }
    }


def test_duplicate_invitation_registration_username_is_sanitized_and_retryable(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    _bootstrap(client)
    invitation = client.post(
        "/api/family-access/v1/people/existing-person/invitations",
        headers=_csrf_headers(client),
        json={
            "role": "caregiver",
            "optional_scopes": [],
            "expires_at": "2027-08-02T10:00:00+00:00",
            "confirm_full_owner_access": False,
        },
    )
    assert invitation.status_code == 201, invitation.text
    secret = invitation.json()["secret"]

    duplicate = client.post(
        "/api/family-access/v1/invite/register",
        headers=SAME_ORIGIN,
        json={
            "secret": secret,
            "username": "OWNER",
            "display_name": "Duplicate",
            "password": "duplicate password value",
            "confirm_full_owner_access": False,
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error": {
            "code": "conflict",
            "message": "The requested state conflicts with current state.",
        }
    }
    assert secret not in duplicate.text
    assert "UNIQUE" not in duplicate.text
    assert "sqlite" not in duplicate.text.lower()
    retry = client.post(
        "/api/family-access/v1/invite/preview",
        headers=SAME_ORIGIN,
        json={"secret": secret},
    )
    assert retry.status_code == 200


def test_second_own_person_creation_is_sanitized_conflict_and_fully_rolls_back(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    bootstrap = client.post(
        "/api/family-access/v1/bootstrap",
        headers=SAME_ORIGIN,
        json={
            "username": "owner",
            "display_name": "Owner",
            "password": "correct horse battery",
        },
    )
    assert bootstrap.status_code == 201, bootstrap.text
    first = client.post(
        "/api/family-access/v1/people",
        headers=_csrf_headers(client),
        json={
            "display_name": "First self profile",
            "confirm_owner_assignment": True,
            "link_as_own": True,
        },
    )
    assert first.status_code == 201, first.text
    runtime = main_module.app.state.product_core_runtime
    tables = (
        "people",
        "person_access_assignments",
        "person_access_consent_history",
        "own_person_links",
        "access_audit_events",
    )
    with runtime.database.connect() as connection:
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

    second = client.post(
        "/api/family-access/v1/people",
        headers=_csrf_headers(client),
        json={
            "display_name": "Second self profile",
            "confirm_owner_assignment": True,
            "link_as_own": True,
        },
    )

    assert second.status_code == 409
    assert second.json() == {
        "error": {
            "code": "conflict",
            "message": "The requested state conflicts with current state.",
        }
    }
    assert "UNIQUE" not in second.text
    assert "sqlite" not in second.text.lower()
    with runtime.database.connect() as connection:
        after = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
        orphan = connection.execute(
            "SELECT 1 FROM people WHERE display_name = 'Second self profile'"
        ).fetchone()
    assert after == before
    assert orphan is None


def _assert_sanitized_validation(response_text: str, *plaintext_values: str) -> None:
    payload = __import__("json").loads(response_text)
    assert payload["error"]["code"] == "request_validation_failed"
    for field in payload["error"]["fields"]:
        assert set(field) == {"loc", "type"}
    assert '"input"' not in response_text
    for value in plaintext_values:
        assert value not in response_text


def test_family_access_validation_never_echoes_plaintext_inputs(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    short_bootstrap_password = "short-pass"
    bootstrap = client.post(
        "/api/family-access/v1/bootstrap",
        headers=SAME_ORIGIN,
        json={
            "username": "owner",
            "display_name": "Owner",
            "password": short_bootstrap_password,
        },
    )
    assert bootstrap.status_code == 422
    _assert_sanitized_validation(bootstrap.text, short_bootstrap_password)

    empty_login_secret = ""
    login = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "", "password": empty_login_secret},
    )
    assert login.status_code == 422
    _assert_sanitized_validation(login.text)

    _bootstrap(client)
    short_new_password = "tiny-pass"
    password = client.post(
        "/api/family-access/v1/password:change",
        headers=_csrf_headers(client),
        json={
            "current_password": "correct horse battery",
            "new_password": short_new_password,
        },
    )
    assert password.status_code == 422
    _assert_sanitized_validation(password.text, short_new_password)

    oversized_secret = "private-invitation-code-" + ("x" * 512)
    preview = client.post(
        "/api/family-access/v1/invite/preview",
        headers=SAME_ORIGIN,
        json={"secret": oversized_secret},
    )
    assert preview.status_code == 422
    _assert_sanitized_validation(preview.text, oversized_secret)


def test_empty_bootstrap_reports_admin_state_without_implicit_person_role(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    response = client.post(
        "/api/family-access/v1/bootstrap",
        headers=SAME_ORIGIN,
        json={
            "username": "admin",
            "display_name": "Installation admin",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["installation_admin"] is True
    assert payload["owner_assignment_count"] == 0
    assert payload["owner_assignments"] == []
    assert "role" not in payload
    assert "scopes" not in payload

    actor_id = payload["actor"]["actor_id"]
    runtime = main_module.app.state.family_access_runtime
    assert (
        runtime.service.authorize_person(actor_id, "existing-person", "person.read").allowed
        is False
    )


def test_active_person_requires_current_access_and_can_be_cleared(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    _bootstrap(client)
    selected = client.put(
        "/api/family-access/v1/active-person",
        headers=_csrf_headers(client),
        json={"person_id": "existing-person"},
    )
    assert selected.status_code == 204
    assert client.get("/api/family-access/v1/me").json()["active_person_id"] == "existing-person"

    cleared = client.put(
        "/api/family-access/v1/active-person",
        headers=_csrf_headers(client),
        json={"person_id": None},
    )
    assert cleared.status_code == 204
    assert client.get("/api/family-access/v1/me").json()["active_person_id"] is None

    runtime = main_module.app.state.product_core_runtime
    with runtime.database.connect() as connection:
        connection.execute("UPDATE people SET is_active = 0 WHERE person_id = 'existing-person'")
    denied = client.put(
        "/api/family-access/v1/active-person",
        headers=_csrf_headers(client),
        json={"person_id": "existing-person"},
    )
    assert denied.status_code == 404
    assert client.get("/api/family-access/v1/me").json()["active_person_id"] is None


def test_malformed_stored_assignment_scopes_return_privacy_safe_person_denial(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    _bootstrap(client)
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.connect() as connection:
        connection.execute(
            "UPDATE person_access_assignments SET scopes_json = '[{}]' "
            "WHERE person_id = 'existing-person'"
        )

    response = client.put(
        "/api/family-access/v1/active-person",
        headers=_csrf_headers(client),
        json={"person_id": "existing-person"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "person_not_found",
            "message": "Person was not found.",
        }
    }


def test_password_change_and_actor_deactivation_invalidate_all_sessions_end_to_end(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    payload = _bootstrap(client)
    owner_id = payload["actor"]["actor_id"]
    runtime = main_module.app.state.family_access_runtime
    first_token = client.cookies.get("opencare_session")
    assert first_token is not None
    second_login = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "owner", "password": "correct horse battery"},
    )
    assert second_login.status_code == 200
    second_token = client.cookies.get("opencare_session")
    assert second_token is not None and second_token != first_token

    changed = client.post(
        "/api/family-access/v1/password:change",
        headers=_csrf_headers(client),
        json={
            "current_password": "correct horse battery",
            "new_password": "new correct horse battery",
        },
    )
    assert changed.status_code == 204
    assert runtime.sessions.resolve(first_token) is None
    assert runtime.sessions.resolve(second_token) is None

    owner_login = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "owner", "password": "new correct horse battery"},
    )
    assert owner_login.status_code == 200
    owner_token = client.cookies.get("opencare_session")
    assert owner_token is not None
    second_admin = runtime.service.create_local_actor(
        owner_id,
        username="second-admin",
        display_name="Second admin",
        password="second admin password",
        installation_admin=True,
    )
    runtime.service.grant_assignment(
        owner_id,
        "existing-person",
        second_admin.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )
    admin_login = client.post(
        "/api/family-access/v1/login",
        headers=SAME_ORIGIN,
        json={"username": "second-admin", "password": "second admin password"},
    )
    assert admin_login.status_code == 200
    deactivated = client.post(
        f"/api/family-access/v1/actors/{owner_id}:deactivate",
        headers=_csrf_headers(client),
        json={},
    )
    assert deactivated.status_code == 204
    assert runtime.sessions.resolve(owner_token) is None


def test_password_epoch_rejects_old_session_when_bulk_invalidation_fails(
    family_access_client: TestClient,
) -> None:
    client = family_access_client
    _bootstrap(client)
    runtime = main_module.app.state.family_access_runtime
    old_token = client.cookies.get("opencare_session")
    assert old_token is not None

    def fail_invalidation(_actor_id: str) -> None:
        raise sqlite3.OperationalError("session store unavailable")

    runtime.service.session_invalidator = fail_invalidation
    changed = client.post(
        "/api/family-access/v1/password:change",
        headers=_csrf_headers(client),
        json={
            "current_password": "correct horse battery",
            "new_password": "new correct horse battery",
        },
    )
    assert changed.status_code == 204
    assert runtime.sessions.resolve(old_token) is not None

    client.cookies.set("opencare_session", old_token)
    denied = client.get("/api/family-access/v1/me")

    assert denied.status_code == 401
    assert runtime.sessions.resolve(old_token) is None
