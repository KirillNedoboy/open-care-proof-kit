import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.family_access.errors import (
    AuditWriteError,
    AuthenticationError,
    BootstrapUnavailableError,
    ConfirmationRequiredError,
    ConflictError,
    InvitationUnavailableError,
    LastAdministratorError,
    LastOwnerError,
    NotFoundError,
    PersonAccessDeniedError,
)
from app.family_access.models import InvalidStoredScopes
from app.family_access.policy import CAREGIVER_BASE_SCOPES, OWNER_SCOPES
from app.family_access.repository import FamilyAccessRepository
from app.family_access.service import FamilyAccessService
from app.product_core.migrations import PRODUCT_MIGRATIONS, MigrationRunner
from app.product_core.sqlite import SQLiteDatabase


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"family-id-{self.value}"


NOW = datetime(2026, 8, 2, 10, tzinfo=UTC)


def _service(tmp_path: Path, **kwargs: object) -> FamilyAccessService:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        timestamp = NOW.isoformat()
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
            ("existing-person", "Existing profile", None, timestamp, timestamp),
        )
    return FamilyAccessService(
        database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_bootstrap_is_atomic_fixed_owner_and_authentication_uses_dummy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    assert service.bootstrap_available() is True
    with pytest.raises(ConfirmationRequiredError):
        service.bootstrap(
            username="owner-without-confirmation",
            display_name="Owner",
            password="correct horse battery",
            person_ids=["existing-person"],
            confirm_full_owner_access=False,
        )
    assert service.bootstrap_available() is True
    actor = service.bootstrap(
        username="  ＡdMiN ",
        display_name="Local owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        own_person_id="existing-person",
        confirm_full_owner_access=True,
    )
    assert service.bootstrap_available() is False
    assert actor.username_normalized == "admin"
    assert service.authenticate("ADMIN", "correct horse battery") == actor
    assert service.authenticate("ADMIN", "wrong password value") is None

    dummy_calls: list[str] = []
    monkeypatch.setattr(
        "app.family_access.service.dummy_verify_password",
        lambda password: dummy_calls.append(password),
    )
    assert service.authenticate("unknown", "never persisted password") is None
    assert dummy_calls == ["never persisted password"]

    decision = service.authorize_person(actor.actor_id, "existing-person", "vault.export")
    assert decision.allowed is True
    with service.database.connect() as connection:
        assignment = connection.execute(
            "SELECT role, scopes_json FROM person_access_assignments"
        ).fetchone()
        own_link_count = connection.execute("SELECT COUNT(*) FROM own_person_links").fetchone()[0]
        stored = connection.execute(
            "SELECT algorithm, algorithm_version, salt, verifier FROM actor_credentials"
        ).fetchone()
        database_bytes = service.database.path.read_bytes()
    assert assignment[0] == "owner"
    assert set(__import__("json").loads(assignment[1])) == OWNER_SCOPES
    assert own_link_count == 1
    assert tuple(stored[:2]) == ("scrypt", 1)
    assert len(stored[2]) >= 16 and len(stored[3]) == 64
    assert b"correct horse battery" not in database_bytes

    with pytest.raises(BootstrapUnavailableError):
        service.bootstrap(
            username="second",
            display_name="Second",
            password="another long password",
        )


def test_password_change_replaces_active_credential_and_invalidates_old_password(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    actor = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
    )

    service.change_password(
        actor.actor_id,
        "correct horse battery",
        "replacement password value",
    )

    assert service.authenticate("owner", "correct horse battery") is None
    assert service.authenticate("owner", "replacement password value") == actor
    with service.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM actor_credentials WHERE actor_id = ?",
            (actor.actor_id,),
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM actor_credentials "
            "WHERE actor_id = ? AND revoked_at IS NULL",
            (actor.actor_id,),
        ).fetchone()[0] == 1


def test_atomic_person_creation_requires_confirmation_and_rolls_back_on_audit_failure(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    actor = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
    )
    with pytest.raises(ConfirmationRequiredError):
        service.create_person(
            actor.actor_id,
            display_name="Child",
            date_of_birth=None,
            confirm_owner_assignment=False,
        )

    person_id = service.create_person(
        actor.actor_id,
        display_name="Child",
        date_of_birth=None,
        confirm_owner_assignment=True,
        link_as_own=True,
    )
    assert service.authorize_person(actor.actor_id, person_id, "access.manage").allowed

    def fail_audit(_connection: sqlite3.Connection, _event: dict[str, str | None]) -> None:
        raise AuditWriteError("forced audit failure")

    failing = FamilyAccessService(
        service.database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        audit_writer=fail_audit,
    )
    with pytest.raises(AuditWriteError):
        failing.create_person(
            actor.actor_id,
            display_name="Rolled back",
            date_of_birth=None,
            confirm_owner_assignment=True,
        )
    with service.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM people WHERE display_name = 'Rolled back'"
            ).fetchone()[0]
            == 0
        )


def test_invitation_hash_only_confirmation_one_time_and_existing_actor_acceptance(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    with pytest.raises(ConfirmationRequiredError):
        service.create_invitation(
            owner.actor_id,
            "existing-person",
            role="owner",
            optional_scopes=set(),
            expires_at=NOW + timedelta(days=1),
            confirm_full_owner_access=False,
        )

    invitation = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="caregiver",
        optional_scopes={"vault.export"},
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=False,
    )
    assert invitation.role == "caregiver"
    assert invitation.scopes == CAREGIVER_BASE_SCOPES | {"vault.export"}
    assert len(invitation.secret) >= 43
    with service.database.connect() as connection:
        stored_hash = connection.execute(
            "SELECT secret_hash FROM access_invitations WHERE invitation_id = ?",
            (invitation.invitation_id,),
        ).fetchone()[0]
    assert stored_hash == hashlib.sha256(invitation.secret.encode()).digest()
    assert invitation.secret.encode() not in service.database.path.read_bytes()

    preview = service.preview_invitation(invitation.secret)
    assert preview.role == "caregiver"
    caregiver = service.register_invitation(
        invitation.secret,
        username="caregiver",
        display_name="Caregiver",
        password="caregiver password",
        confirm_full_owner_access=False,
    )
    assert service.authorize_person(caregiver.actor_id, "existing-person", "vault.export").allowed
    with pytest.raises(InvitationUnavailableError) as replay:
        service.preview_invitation(invitation.secret)
    with pytest.raises(InvitationUnavailableError) as invalid:
        service.preview_invitation("not a valid invitation secret")
    assert str(replay.value) == str(invalid.value)

    invitation2 = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="caregiver",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=False,
    )
    service.revoke_assignment(owner.actor_id, "existing-person", caregiver.actor_id)
    service.accept_invitation(
        caregiver.actor_id,
        invitation2.secret,
        confirm_full_owner_access=False,
    )
    assert service.authorize_person(caregiver.actor_id, "existing-person", "person.read").allowed


def test_family_relationships_are_context_only_and_denial_audit_failure_stays_denied(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    child_id = service.create_person(
        owner.actor_id,
        display_name="Child",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    family = service.create_family(owner.actor_id, "Household")
    service.add_membership(owner.actor_id, family.family_id, "existing-person")
    service.add_membership(owner.actor_id, family.family_id, child_id)
    relationship = service.create_relationship(
        owner.actor_id,
        family.family_id,
        person_id="existing-person",
        related_person_id=child_id,
        relationship_type="parent",
    )
    assert relationship.relationship_type == "parent"

    invitation = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="caregiver",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=False,
    )
    caregiver = service.register_invitation(
        invitation.secret,
        username="caregiver",
        display_name="Caregiver",
        password="caregiver password",
        confirm_full_owner_access=False,
    )
    assert service.authorize_person(caregiver.actor_id, child_id, "person.read").allowed is False

    def fail_audit(_connection: sqlite3.Connection, _event: dict[str, str | None]) -> None:
        raise sqlite3.OperationalError("sensitive value must not be logged")

    failing = FamilyAccessService(
        service.database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        audit_writer=fail_audit,
    )
    with pytest.raises(PersonAccessDeniedError):
        failing.require_person_access(caregiver.actor_id, child_id, "person.read")
    assert "sensitive value" not in caplog.text
    assert "family_access_denial_audit_failed" in caplog.text


def test_actor_deactivation_protects_last_admin_and_owner_then_revokes_atomically(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    first = service.bootstrap(
        username="first",
        display_name="First",
        password="correct horse battery",
        person_ids=["existing-person"],
        own_person_id="existing-person",
        confirm_full_owner_access=True,
    )
    with pytest.raises(LastAdministratorError):
        service.deactivate_actor(first.actor_id, first.actor_id)

    second = service.create_local_actor(
        first.actor_id,
        username="second",
        display_name="Second",
        password="second actor password",
        installation_admin=True,
    )
    service.grant_assignment(
        first.actor_id,
        "existing-person",
        second.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )

    def fail_audit(_connection: sqlite3.Connection, _event: dict[str, str | None]) -> None:
        raise AuditWriteError("forced deactivation audit failure")

    failing = FamilyAccessService(
        service.database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        audit_writer=fail_audit,
    )
    with pytest.raises(AuditWriteError):
        failing.deactivate_actor(second.actor_id, first.actor_id)
    with service.database.connect() as connection:
        assert connection.execute(
            "SELECT status FROM actors WHERE actor_id = ?", (first.actor_id,)
        ).fetchone()[0] == "active"
        assert connection.execute(
            "SELECT COUNT(*) FROM own_person_links WHERE actor_id = ? AND is_active = 1",
            (first.actor_id,),
        ).fetchone()[0] == 1

    service.deactivate_actor(second.actor_id, first.actor_id)
    with service.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT status FROM actors WHERE actor_id = ?", (first.actor_id,)
            ).fetchone()[0]
            == "disabled"
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM own_person_links WHERE actor_id = ? AND is_active = 1",
                (first.actor_id,),
            ).fetchone()[0]
            == 0
        )
        deactivation_actions = {
            row[0]
            for row in connection.execute(
                "SELECT action_code FROM access_audit_events WHERE actor_id = ?",
                (second.actor_id,),
            ).fetchall()
        }
        assert "own_person_link.revoke" in deactivation_actions
        assert "admin.revoke" in deactivation_actions
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM person_access_assignments "
                "WHERE actor_id = ? AND is_active = 1",
                (first.actor_id,),
            ).fetchone()[0]
            == 0
        )
    assert service.authenticate("first", "correct horse battery") is None

    with pytest.raises(LastAdministratorError):
        service.deactivate_actor(second.actor_id, second.actor_id)
    with pytest.raises(LastOwnerError):
        service.revoke_assignment(second.actor_id, "existing-person", second.actor_id)


def test_sensitive_write_rechecks_person_access_inside_immediate_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    first = service.bootstrap(
        username="first",
        display_name="First",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    second = service.create_local_actor(
        first.actor_id,
        username="second",
        display_name="Second",
        password="second actor password",
    )
    recipient = service.create_local_actor(
        first.actor_id,
        username="recipient",
        display_name="Recipient",
        password="recipient password value",
    )
    service.grant_assignment(
        first.actor_id,
        "existing-person",
        second.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )
    original_uow = service.database.uow
    revoked = False

    def raced_uow(*, begin_mode: str = "DEFERRED"):  # type: ignore[no-untyped-def]
        nonlocal revoked
        if begin_mode == "IMMEDIATE" and not revoked:
            revoked = True
            with service.database.connect() as connection:
                connection.execute(
                    """
                    UPDATE person_access_assignments
                    SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                    WHERE actor_id = ? AND person_id = ? AND is_active = 1
                    """,
                    (NOW.isoformat(), second.actor_id, first.actor_id, "existing-person"),
                )
        return original_uow(begin_mode=begin_mode)  # type: ignore[arg-type]

    monkeypatch.setattr(service.database, "uow", raced_uow)

    with pytest.raises(PersonAccessDeniedError):
        service.grant_assignment(
            first.actor_id,
            "existing-person",
            recipient.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )
    assert service.authorize_person(
        recipient.actor_id, "existing-person", "person.read"
    ).allowed is False
    with service.database.connect() as connection:
        denied = connection.execute(
            """
            SELECT outcome, reason_code FROM access_audit_events
            WHERE actor_id = ? AND target_id = 'existing-person'
                  AND action_code = 'person_access.check'
            ORDER BY created_at DESC LIMIT 1
            """,
            (first.actor_id,),
        ).fetchone()
    assert tuple(denied) == ("denied", "person_access_denied")


def test_person_scoped_read_authorizes_inside_its_transaction_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    first = service.bootstrap(
        username="first",
        display_name="First",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    second = service.create_local_actor(
        first.actor_id,
        username="second",
        display_name="Second",
        password="second actor password",
    )
    service.grant_assignment(
        first.actor_id,
        "existing-person",
        second.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )
    original_uow = service.database.uow
    revoked = False

    def raced_uow(*, begin_mode: str = "DEFERRED"):  # type: ignore[no-untyped-def]
        nonlocal revoked
        if begin_mode == "DEFERRED" and not revoked:
            revoked = True
            with service.database.connect() as connection:
                connection.execute(
                    """
                    UPDATE person_access_assignments
                    SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                    WHERE actor_id = ? AND person_id = ? AND is_active = 1
                    """,
                    (NOW.isoformat(), second.actor_id, first.actor_id, "existing-person"),
                )
        return original_uow(begin_mode=begin_mode)  # type: ignore[arg-type]

    monkeypatch.setattr(service.database, "uow", raced_uow)

    with pytest.raises(PersonAccessDeniedError):
        service.list_assignments(first.actor_id, "existing-person")
    with service.database.connect() as connection:
        denied_count = connection.execute(
            """
            SELECT COUNT(*) FROM access_audit_events
            WHERE actor_id = ? AND target_id = 'existing-person'
                  AND outcome = 'denied' AND reason_code = 'person_access_denied'
            """,
            (first.actor_id,),
        ).fetchone()[0]
    assert denied_count == 1


def test_mutation_denial_audit_failure_preserves_exact_access_denial(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    outsider = service.create_local_actor(
        owner.actor_id,
        username="outsider",
        display_name="Outsider",
        password="outsider password value",
    )
    attempted_audits: list[dict[str, str | None]] = []

    def fail_audit(_connection: sqlite3.Connection, event: dict[str, str | None]) -> None:
        attempted_audits.append(event)
        raise sqlite3.OperationalError("audit storage unavailable")

    failing = FamilyAccessService(
        service.database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        audit_writer=fail_audit,
    )

    with pytest.raises(PersonAccessDeniedError) as denied:
        failing.grant_assignment(
            outsider.actor_id,
            "existing-person",
            outsider.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )
    assert str(denied.value) == "Person was not found."
    assert [(item["outcome"], item["reason_code"]) for item in attempted_audits] == [
        ("denied", "person_access_denied")
    ]


def test_admin_can_claim_only_an_active_unclaimed_migrated_person_as_owner(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:4]).migrate()
    with database.connect() as connection:
        for person_id in ("selected-person", "unclaimed-person", "inactive-person"):
            connection.execute(
                "INSERT INTO people VALUES (?, ?, NULL, ?, ?, 1)",
                (person_id, person_id, NOW.isoformat(), NOW.isoformat()),
            )
        connection.execute(
            "UPDATE people SET is_active = 0 WHERE person_id = 'inactive-person'"
        )
    database.migrate()
    service = FamilyAccessService(database, clock=lambda: NOW, id_factory=SequenceIds())
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
        person_ids=["selected-person"],
        confirm_full_owner_access=True,
    )
    second_admin = service.create_local_actor(
        admin.actor_id,
        username="second-admin",
        display_name="Second admin",
        password="second admin password",
        installation_admin=True,
    )
    recipient = service.create_local_actor(
        admin.actor_id,
        username="recipient",
        display_name="Recipient",
        password="recipient password value",
    )

    assert service.authorize_person(admin.actor_id, "selected-person", "access.manage").allowed
    for scope in ("person.read", "vault.export", "chat.use"):
        assert service.authorize_person(admin.actor_id, "unclaimed-person", scope).allowed is False
    with pytest.raises(PersonAccessDeniedError):
        service.list_assignments(admin.actor_id, "unclaimed-person")
    with pytest.raises(PersonAccessDeniedError):
        service.grant_assignment(
            admin.actor_id,
            "unclaimed-person",
            recipient.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )
    with pytest.raises(ConfirmationRequiredError):
        service.grant_assignment(
            admin.actor_id,
            "unclaimed-person",
            recipient.actor_id,
            role="owner",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )

    assignment = service.grant_assignment(
        admin.actor_id,
        "unclaimed-person",
        recipient.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )
    assert assignment.scopes == OWNER_SCOPES
    assert service.authorize_person(recipient.actor_id, "unclaimed-person", "access.manage").allowed
    with pytest.raises(PersonAccessDeniedError):
        service.grant_assignment(
            second_admin.actor_id,
            "unclaimed-person",
            second_admin.actor_id,
            role="owner",
            optional_scopes=set(),
            confirm_full_owner_access=True,
        )
    with pytest.raises(PersonAccessDeniedError):
        service.grant_assignment(
            admin.actor_id,
            "inactive-person",
            recipient.actor_id,
            role="owner",
            optional_scopes=set(),
            confirm_full_owner_access=True,
        )

    with database.connect() as connection:
        audit = connection.execute(
            """
            SELECT action_code, target_id, reason_code FROM access_audit_events
            WHERE action_code = 'admin.unclaimed_person.claim'
            """
        ).fetchall()
    assert [tuple(row) for row in audit] == [
        ("admin.unclaimed_person.claim", "unclaimed-person", "admin_owner_grant")
    ]


def test_admin_owner_invitation_requires_confirmation_and_has_exact_lifecycle(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
    )

    with pytest.raises(PersonAccessDeniedError):
        service.create_invitation(
            admin.actor_id,
            "existing-person",
            role="caregiver",
            optional_scopes=set(),
            expires_at=NOW + timedelta(days=1),
            confirm_full_owner_access=False,
        )
    with pytest.raises(ConfirmationRequiredError):
        service.create_invitation(
            admin.actor_id,
            "existing-person",
            role="owner",
            optional_scopes=set(),
            expires_at=NOW + timedelta(days=1),
            confirm_full_owner_access=False,
        )

    invitation = service.create_invitation(
        admin.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    competing_admin_invitation = service.create_invitation(
        admin.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    preview = service.preview_invitation(invitation.secret)
    assert preview.role == "owner"
    assert preview.scopes == OWNER_SCOPES
    with service.database.connect() as connection:
        invitation_audit = connection.execute(
            """
            SELECT action_code, target_id, reason_code FROM access_audit_events
            WHERE action_code = 'admin.unclaimed_person.invitation'
            """
        ).fetchone()
    assert tuple(invitation_audit) == (
        "admin.unclaimed_person.invitation",
        "existing-person",
        "admin_owner_invitation",
    )
    with pytest.raises(ConfirmationRequiredError):
        service.register_invitation(
            invitation.secret,
            username="owner-no-confirm",
            display_name="Owner",
            password="owner password value",
            confirm_full_owner_access=False,
        )
    assert service.preview_invitation(invitation.secret).scopes == OWNER_SCOPES
    owner = service.register_invitation(
        invitation.secret,
        username="owner-confirmed",
        display_name="Owner",
        password="owner password value",
        confirm_full_owner_access=True,
    )
    assert service.authorize_person(owner.actor_id, "existing-person", "access.manage").allowed
    with pytest.raises(InvitationUnavailableError):
        service.preview_invitation(competing_admin_invitation.secret)
    with pytest.raises(InvitationUnavailableError) as replay:
        service.preview_invitation(invitation.secret)

    existing_actor = service.create_local_actor(
        admin.actor_id,
        username="existing-actor",
        display_name="Existing actor",
        password="existing actor password",
    )
    accepted_invitation = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    assert service.preview_invitation(accepted_invitation.secret).scopes == OWNER_SCOPES
    with pytest.raises(ConfirmationRequiredError):
        service.accept_invitation(
            existing_actor.actor_id,
            accepted_invitation.secret,
            confirm_full_owner_access=False,
        )
    accepted = service.accept_invitation(
        existing_actor.actor_id,
        accepted_invitation.secret,
        confirm_full_owner_access=True,
    )
    assert accepted.role == "owner"
    assert accepted.scopes == OWNER_SCOPES
    with pytest.raises(InvitationUnavailableError) as accepted_replay:
        service.accept_invitation(
            existing_actor.actor_id,
            accepted_invitation.secret,
            confirm_full_owner_access=True,
        )

    revoked = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    service.revoke_invitation(owner.actor_id, "existing-person", revoked.invitation_id)
    with pytest.raises(InvitationUnavailableError) as revoked_error:
        service.preview_invitation(revoked.secret)
    with pytest.raises(InvitationUnavailableError) as revoked_accept:
        service.accept_invitation(
            existing_actor.actor_id,
            revoked.secret,
            confirm_full_owner_access=True,
        )

    expired = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    with service.database.connect() as connection:
        connection.execute(
            "UPDATE access_invitations SET expires_at = ? WHERE invitation_id = ?",
            ((NOW - timedelta(seconds=1)).isoformat(), expired.invitation_id),
        )
    with pytest.raises(InvitationUnavailableError) as expired_error:
        service.preview_invitation(expired.secret)
    with pytest.raises(InvitationUnavailableError) as expired_register:
        service.register_invitation(
            expired.secret,
            username="expired-owner",
            display_name="Expired owner",
            password="expired owner password",
            confirm_full_owner_access=True,
        )
    assert {
        str(replay.value),
        str(accepted_replay.value),
        str(revoked_error.value),
        str(revoked_accept.value),
        str(expired_error.value),
        str(expired_register.value),
    } == {"Invitation is unavailable."}


def test_admin_can_revoke_only_own_owner_claim_invitation_while_person_is_ownerless(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
    )
    second_admin = service.create_local_actor(
        admin.actor_id,
        username="second-admin",
        display_name="Second admin",
        password="second admin password",
        installation_admin=True,
    )
    recipient = service.create_local_actor(
        admin.actor_id,
        username="recipient",
        display_name="Recipient",
        password="recipient password value",
    )
    invitation = service.create_invitation(
        admin.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )
    stale_after_claim = service.create_invitation(
        admin.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )

    assert service.authorize_person(
        admin.actor_id, "existing-person", "person.read"
    ).allowed is False
    with pytest.raises(PersonAccessDeniedError):
        service.revoke_invitation(
            second_admin.actor_id, "existing-person", invitation.invitation_id
        )

    service.revoke_invitation(admin.actor_id, "existing-person", invitation.invitation_id)
    with pytest.raises(InvitationUnavailableError):
        service.preview_invitation(invitation.secret)
    with service.database.connect() as connection:
        admin_audit = connection.execute(
            """
            SELECT action_code, target_id, reason_code
            FROM access_audit_events
            WHERE action_code = 'admin.unclaimed_person.invitation_revoke'
            """
        ).fetchone()
    assert tuple(admin_audit) == (
        "admin.unclaimed_person.invitation_revoke",
        "existing-person",
        "admin_owner_invitation_revoke",
    )

    service.grant_assignment(
        admin.actor_id,
        "existing-person",
        recipient.actor_id,
        role="owner",
        optional_scopes=set(),
        confirm_full_owner_access=True,
    )
    with pytest.raises(PersonAccessDeniedError):
        service.revoke_invitation(
            admin.actor_id,
            "existing-person",
            stale_after_claim.invitation_id,
        )
    service.revoke_invitation(
        recipient.actor_id,
        "existing-person",
        stale_after_claim.invitation_id,
    )


def test_admin_owner_claim_invitation_revoke_rolls_back_when_audit_fails(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
    )
    invitation = service.create_invitation(
        admin.actor_id,
        "existing-person",
        role="owner",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=True,
    )

    def fail_audit(_connection: sqlite3.Connection, _event: dict[str, str | None]) -> None:
        raise AuditWriteError("forced invitation revoke audit failure")

    failing = FamilyAccessService(
        service.database,
        clock=lambda: NOW,
        id_factory=SequenceIds(),
        audit_writer=fail_audit,
    )
    with pytest.raises(AuditWriteError):
        failing.revoke_invitation(
            admin.actor_id, "existing-person", invitation.invitation_id
        )

    assert service.preview_invitation(invitation.secret).role == "owner"


def test_corrupt_assignment_and_invitation_scopes_cannot_authorize_or_write(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    recipient = service.create_local_actor(
        owner.actor_id,
        username="recipient",
        display_name="Recipient",
        password="recipient password value",
    )
    invitation = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="caregiver",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=False,
    )
    with service.database.connect() as connection:
        connection.execute(
            "UPDATE person_access_assignments SET scopes_json = '[{}]' "
            "WHERE actor_id = ? AND person_id = 'existing-person'",
            (owner.actor_id,),
        )
        connection.execute(
            "UPDATE access_invitations SET scopes_json = '[\"access.manage\"]' "
            "WHERE invitation_id = ?",
            (invitation.invitation_id,),
        )

    decision = service.authorize_person(owner.actor_id, "existing-person", "access.manage")
    assert decision.allowed is False
    assert decision.reason_code == "invalid_assignment_scopes"
    with pytest.raises(PersonAccessDeniedError):
        service.grant_assignment(
            owner.actor_id,
            "existing-person",
            recipient.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )
    with pytest.raises(InvitationUnavailableError):
        service.preview_invitation(invitation.secret)


def test_duplicate_active_assignment_is_a_stable_conflict_and_rolls_back_consent(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    caregiver = service.create_local_actor(
        owner.actor_id,
        username="caregiver",
        display_name="Caregiver",
        password="caregiver password value",
    )
    service.grant_assignment(
        owner.actor_id,
        "existing-person",
        caregiver.actor_id,
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
    )
    with service.database.connect() as connection:
        consent_count = connection.execute(
            "SELECT COUNT(*) FROM person_access_consent_history"
        ).fetchone()[0]

    with pytest.raises(ConflictError, match="active assignment"):
        service.grant_assignment(
            owner.actor_id,
            "existing-person",
            caregiver.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )

    with service.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM person_access_consent_history"
        ).fetchone()[0] == consent_count


def test_duplicate_membership_and_relationship_are_stable_conflicts(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    child_id = service.create_person(
        owner.actor_id,
        display_name="Child",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    family = service.create_family(owner.actor_id, "Household")
    service.add_membership(owner.actor_id, family.family_id, "existing-person")
    service.add_membership(owner.actor_id, family.family_id, child_id)
    service.create_relationship(
        owner.actor_id,
        family.family_id,
        person_id="existing-person",
        related_person_id=child_id,
        relationship_type="parent",
    )

    with pytest.raises(ConflictError, match="active membership"):
        service.add_membership(owner.actor_id, family.family_id, "existing-person")
    with pytest.raises(ConflictError, match="active relationship"):
        service.create_relationship(
            owner.actor_id,
            family.family_id,
            person_id="existing-person",
            related_person_id=child_id,
            relationship_type="parent",
        )

    with service.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM family_memberships WHERE is_active = 1"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM person_relationships WHERE is_active = 1"
        ).fetchone()[0] == 1


def test_archived_family_rejects_all_membership_and_relationship_mutations(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    child_id = service.create_person(
        owner.actor_id,
        display_name="Child",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    detached_id = service.create_person(
        owner.actor_id,
        display_name="Detached",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    new_member_id = service.create_person(
        owner.actor_id,
        display_name="New member",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    family = service.create_family(owner.actor_id, "Household")
    service.add_membership(owner.actor_id, family.family_id, "existing-person")
    service.add_membership(owner.actor_id, family.family_id, child_id)
    detached_membership = service.add_membership(
        owner.actor_id, family.family_id, detached_id
    )
    relationship = service.create_relationship(
        owner.actor_id,
        family.family_id,
        person_id="existing-person",
        related_person_id=child_id,
        relationship_type="parent",
    )
    service.archive_family(owner.actor_id, family.family_id)

    with pytest.raises(NotFoundError):
        service.create_relationship(
            owner.actor_id,
            family.family_id,
            person_id="existing-person",
            related_person_id=child_id,
            relationship_type="guardian",
        )
    with pytest.raises(NotFoundError):
        service.end_relationship(owner.actor_id, family.family_id, relationship.relationship_id)
    with pytest.raises(NotFoundError):
        service.end_membership(
            owner.actor_id, family.family_id, detached_membership.membership_id
        )
    with pytest.raises(NotFoundError):
        service.add_membership(owner.actor_id, family.family_id, new_member_id)

    with service.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM family_memberships WHERE family_id = ? AND is_active = 1",
            (family.family_id,),
        ).fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) FROM person_relationships WHERE family_id = ? AND is_active = 1",
            (family.family_id,),
        ).fetchone()[0] == 1


def test_repository_deserializes_schema_valid_malformed_scopes_without_crashing(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    with service.database.connect() as connection:
        connection.execute(
            "UPDATE person_access_assignments SET scopes_json = '[{}]' "
            "WHERE actor_id = ? AND person_id = 'existing-person'",
            (owner.actor_id,),
        )
        assignment = FamilyAccessRepository(connection).get_active_assignment(
            owner.actor_id, "existing-person"
        )

    assert assignment is not None
    assert isinstance(assignment.scopes, InvalidStoredScopes)


def test_password_change_rechecks_active_actor_inside_immediate_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
    )
    actor = service.create_local_actor(
        admin.actor_id,
        username="actor",
        display_name="Actor",
        password="actor current password",
    )
    original_uow = service.database.uow
    disabled = False

    def raced_uow(*, begin_mode: str = "DEFERRED"):  # type: ignore[no-untyped-def]
        nonlocal disabled
        if begin_mode == "IMMEDIATE" and not disabled:
            disabled = True
            with service.database.connect() as connection:
                connection.execute(
                    """
                    UPDATE actors SET status = 'disabled', disabled_at = ?,
                        disabled_by_actor_id = ? WHERE actor_id = ?
                    """,
                    (NOW.isoformat(), admin.actor_id, actor.actor_id),
                )
        return original_uow(begin_mode=begin_mode)  # type: ignore[arg-type]

    monkeypatch.setattr(service.database, "uow", raced_uow)

    with pytest.raises(AuthenticationError):
        service.change_password(
            actor.actor_id,
            "actor current password",
            "actor replacement password",
        )
    assert service.authenticate("actor", "actor replacement password") is None


def test_invitation_is_unavailable_when_its_person_becomes_inactive(tmp_path: Path) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    invitation = service.create_invitation(
        owner.actor_id,
        "existing-person",
        role="caregiver",
        optional_scopes=set(),
        expires_at=NOW + timedelta(days=1),
        confirm_full_owner_access=False,
    )
    with service.database.connect() as connection:
        connection.execute("UPDATE people SET is_active = 0 WHERE person_id = 'existing-person'")

    with pytest.raises(InvitationUnavailableError):
        service.preview_invitation(invitation.secret)
    with pytest.raises(InvitationUnavailableError):
        service.register_invitation(
            invitation.secret,
            username="caregiver",
            display_name="Caregiver",
            password="caregiver password",
            confirm_full_owner_access=False,
        )


def test_family_reads_filter_corrupt_person_assignments_in_one_snapshot(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    owner = service.bootstrap(
        username="owner",
        display_name="Owner",
        password="correct horse battery",
        person_ids=["existing-person"],
        confirm_full_owner_access=True,
    )
    child_id = service.create_person(
        owner.actor_id,
        display_name="Child",
        date_of_birth=None,
        confirm_owner_assignment=True,
    )
    caregiver = service.create_local_actor(
        owner.actor_id,
        username="caregiver",
        display_name="Caregiver",
        password="caregiver password",
    )
    service.grant_assignment(
        owner.actor_id,
        "existing-person",
        caregiver.actor_id,
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
    )
    family = service.create_family(owner.actor_id, "Household")
    service.add_membership(owner.actor_id, family.family_id, "existing-person")
    service.add_membership(owner.actor_id, family.family_id, child_id)
    service.create_relationship(
        owner.actor_id,
        family.family_id,
        person_id="existing-person",
        related_person_id=child_id,
        relationship_type="parent",
    )
    with service.database.connect() as connection:
        connection.execute(
            "UPDATE person_access_assignments SET scopes_json = '[\"person.read\"]' "
            "WHERE actor_id IN (?, ?) AND person_id = 'existing-person'",
            (owner.actor_id, caregiver.actor_id),
        )

    assert service.list_families(caregiver.actor_id) == []
    family_view = service.get_family(owner.actor_id, family.family_id)
    assert [item["person_id"] for item in family_view["memberships"]] == [child_id]
    assert family_view["relationships"] == []


def test_archive_empty_family_rechecks_active_creator_inside_transaction(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    admin = service.bootstrap(
        username="admin",
        display_name="Admin",
        password="correct horse battery",
    )
    actor = service.create_local_actor(
        admin.actor_id,
        username="family-creator",
        display_name="Family creator",
        password="family creator password",
    )
    family = service.create_family(actor.actor_id, "Empty family")
    with service.database.connect() as connection:
        connection.execute(
            """
            UPDATE actors SET status = 'disabled', disabled_at = ?,
                disabled_by_actor_id = ? WHERE actor_id = ?
            """,
            (NOW.isoformat(), admin.actor_id, actor.actor_id),
        )

    with pytest.raises(AuthenticationError):
        service.archive_family(actor.actor_id, family.family_id)
