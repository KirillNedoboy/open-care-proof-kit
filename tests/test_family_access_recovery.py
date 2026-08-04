from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.family_access.service import FamilyAccessService
from app.family_access.sessions import SessionStore
from app.product_core import backup_cli
from app.product_core.installation_backup import (
    InstallationBackupError,
    InstallationBackupService,
)
from app.product_core.models import Person
from app.product_core.services import SourceService
from app.product_core.sqlite import SQLiteDatabase

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)
V5_TABLES = (
    "actors",
    "actor_credentials",
    "installation_admin_assignments",
    "families",
    "family_memberships",
    "person_relationships",
    "person_access_consent_history",
    "person_access_assignments",
    "own_person_links",
    "access_invitations",
    "access_audit_events",
)


def test_offline_backup_recovery_preserves_v5_state_but_not_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database, sources, service, owner_id, caregiver_id, invitation_secret = (
        _seed_v5_installation(tmp_path)
    )
    credential = service.authenticate_for_session("owner", "correct horse battery")
    assert credential is not None
    session_path = tmp_path / "runtime" / "sessions.sqlite3"
    sessions = SessionStore(session_path, clock=lambda: NOW)
    old_session = sessions.create(owner_id, credential.credential_id)
    backup = tmp_path / "backup"
    recovered = tmp_path / "recovered"

    monkeypatch.setattr(
        backup_cli,
        "load_settings",
        lambda: (_ for _ in ()).throw(AssertionError("offline command loaded HTTP settings")),
    )
    commands = (
        [
            "backup",
            "--database",
            str(database.path),
            "--source-dir",
            str(sources.store.source_dir),
            "--destination",
            str(backup),
        ],
        ["verify", "--backup", str(backup)],
        ["preflight", "--backup", str(backup), "--target-root", str(recovered)],
        [
            "recover",
            "--backup",
            str(backup),
            "--target-root",
            str(recovered),
            "--confirm-maintenance",
        ],
    )
    for command in commands:
        assert backup_cli.main(command) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "valid"

    assert session_path.is_file()
    assert not any(path.name == "sessions.sqlite3" for path in backup.rglob("*"))
    assert not any(path.name == "sessions.sqlite3" for path in recovered.rglob("*"))
    for path in backup.rglob("*"):
        if path.is_file():
            payload = path.read_bytes()
            assert invitation_secret.encode() not in payload
            assert old_session.session_token.encode() not in payload

    with database.connect() as active, sqlite3.connect(
        recovered / "database.sqlite3"
    ) as restored:
        for table in V5_TABLES:
            active_count = active.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            restored_count = restored.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert restored_count == active_count, table
        assert restored.execute(
            "SELECT COUNT(*) FROM person_access_assignments "
            "WHERE actor_id = ? AND is_active = 1",
            (caregiver_id,),
        ).fetchone() == (0,)
        assert restored.execute(
            "SELECT COUNT(*) FROM person_access_consent_history WHERE event_type = 'revoke'"
        ).fetchone()[0] >= 1
        assert restored.execute(
            "SELECT COUNT(*) FROM access_audit_events WHERE action_code = 'assignment.revoke'"
        ).fetchone()[0] >= 1
        assert restored.execute(
            "SELECT state FROM access_invitations"
        ).fetchone() == ("revoked",)
        assert restored.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sessions'"
        ).fetchone() is None

    restored_service = FamilyAccessService(
        SQLiteDatabase(recovered / "database.sqlite3"), clock=lambda: NOW
    )
    restored_owner = restored_service.authenticate_for_session(
        "owner", "correct horse battery"
    )
    assert restored_owner is not None
    assert restored_service.authenticate("caregiver", "caregiver password") is not None
    assert not restored_service.authorize_person(
        caregiver_id, "person-1", "person.read"
    ).allowed

    replacement_sessions = SessionStore(
        tmp_path / "new-runtime" / "sessions.sqlite3", clock=lambda: NOW
    )
    assert replacement_sessions.resolve(old_session.session_token) is None
    new_session = replacement_sessions.create(
        restored_owner.actor.actor_id, restored_owner.credential_id
    )
    assert replacement_sessions.resolve(new_session.session_token) is not None


@pytest.mark.parametrize(
    "table",
    (
        "person_access_consent_history",
        "person_access_assignments",
        "access_invitations",
    ),
)
def test_backup_rejects_invalid_durable_access_policy(
    tmp_path: Path, table: str
) -> None:
    database, sources, _service, _owner_id, _caregiver_id, _secret = (
        _seed_v5_installation(tmp_path)
    )
    with database.connect() as connection:
        if table == "person_access_consent_history":
            connection.execute("DROP TRIGGER consent_history_immutable_update")
        connection.execute(
            f"UPDATE {table} SET scopes_json = ? WHERE rowid = (SELECT MIN(rowid) FROM {table})",
            ('["person.read"]',),
        )

    with pytest.raises(InstallationBackupError, match="family_access_consistency_failed"):
        InstallationBackupService(database.path, sources.store.source_dir).backup(
            tmp_path / "invalid-backup"
        )


def _seed_v5_installation(
    tmp_path: Path,
) -> tuple[SQLiteDatabase, SourceService, FamilyAccessService, str, str, str]:
    database = SQLiteDatabase(tmp_path / "product" / "database.sqlite3")
    database.migrate()
    with database.uow() as uow:
        for person_id, display_name in (
            ("person-1", "First profile"),
            ("person-2", "Second profile"),
        ):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=display_name,
                    created_at=NOW,
                    updated_at=NOW,
                    is_active=True,
                )
            )
    sources = SourceService(database, tmp_path / "product" / "sources")
    service = FamilyAccessService(database, clock=lambda: NOW)
    owner = service.bootstrap(
        username="owner",
        display_name="Installation owner",
        password="correct horse battery",
        person_ids=["person-1", "person-2"],
        own_person_id="person-1",
        confirm_full_owner_access=True,
    )
    caregiver = service.create_local_actor(
        owner.actor_id,
        username="caregiver",
        display_name="Caregiver",
        password="caregiver password",
    )
    assignment = service.grant_assignment(
        owner.actor_id,
        "person-1",
        caregiver.actor_id,
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
    )
    family = service.create_family(owner.actor_id, "Private family")
    service.add_membership(owner.actor_id, family.family_id, "person-1")
    service.add_membership(owner.actor_id, family.family_id, "person-2")
    service.create_relationship(
        owner.actor_id,
        family.family_id,
        person_id="person-1",
        related_person_id="person-2",
        relationship_type="guardian",
    )
    invitation = service.create_invitation(
        owner.actor_id,
        "person-1",
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
        expires_at=NOW + timedelta(days=1),
    )
    service.revoke_invitation(owner.actor_id, "person-1", invitation.invitation_id)
    service.revoke_assignment(owner.actor_id, "person-1", assignment.assignment_id)
    assert invitation.secret.encode() not in database.path.read_bytes()
    return (
        database,
        sources,
        service,
        owner.actor_id,
        caregiver.actor_id,
        invitation.secret,
    )
