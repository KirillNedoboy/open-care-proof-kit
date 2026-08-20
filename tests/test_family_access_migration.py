import sqlite3
from pathlib import Path

import pytest

from app.product_core.migrations import PRODUCT_MIGRATIONS, MigrationRunner
from app.product_core.sqlite import SQLiteDatabase

ACCESS_TABLES = {
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
}

TIMESTAMP = "2026-08-02T10:00:00+00:00"


def _insert_actor(connection: sqlite3.Connection, actor_id: str) -> None:
    connection.execute(
        """
        INSERT INTO actors (actor_id, username_normalized, display_name, status, created_at)
        VALUES (?, ?, ?, 'active', ?)
        """,
        (actor_id, actor_id, actor_id, TIMESTAMP),
    )


def _insert_person(connection: sqlite3.Connection, person_id: str) -> None:
    connection.execute(
        "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
        (person_id, person_id, None, TIMESTAMP, TIMESTAMP),
    )


def _insert_owner(
    connection: sqlite3.Connection,
    *,
    assignment_id: str,
    actor_id: str,
    person_id: str,
) -> None:
    consent_id = f"consent-{assignment_id}"
    connection.execute(
        """
        INSERT INTO person_access_consent_history (
            consent_event_id, event_type, acting_owner_actor_id, recipient_actor_id,
            person_id, role, scopes_json, reason_code, created_at
        ) VALUES (?, 'grant', ?, ?, ?, 'owner', '[\"person.read\"]', 'owner_grant', ?)
        """,
        (consent_id, actor_id, actor_id, person_id, TIMESTAMP),
    )
    connection.execute(
        """
        INSERT INTO person_access_assignments (
            assignment_id, actor_id, person_id, role, scopes_json, consent_event_id,
            granted_by_actor_id, is_active, granted_at
        ) VALUES (?, ?, ?, 'owner', '[\"person.read\"]', ?, ?, 1, ?)
        """,
        (assignment_id, actor_id, person_id, consent_id, actor_id, TIMESTAMP),
    )


def _insert_archived_family_graph(connection: sqlite3.Connection) -> None:
    _insert_actor(connection, "actor-1")
    for person_id in ("person-1", "person-2", "person-3", "person-4"):
        _insert_person(connection, person_id)
    connection.execute(
        "INSERT INTO families VALUES ('family-1', 'Family', 'actor-1', ?, 0, NULL, NULL)",
        (TIMESTAMP,),
    )
    for membership_id, person_id in (
        ("membership-1", "person-1"),
        ("membership-2", "person-2"),
        ("membership-3", "person-3"),
    ):
        connection.execute(
            """
            INSERT INTO family_memberships (
                membership_id, family_id, person_id, created_by_actor_id,
                is_active, created_at
            ) VALUES (?, 'family-1', ?, 'actor-1', 1, ?)
            """,
            (membership_id, person_id, TIMESTAMP),
        )
    connection.execute(
        """
        INSERT INTO person_relationships (
            relationship_id, family_id, person_id, related_person_id,
            relationship_type, created_by_actor_id, is_active, created_at
        ) VALUES (
            'relationship-1', 'family-1', 'person-1', 'person-2',
            'parent', 'actor-1', 1, ?
        )
        """,
        (TIMESTAMP,),
    )
    connection.execute(
        """
        UPDATE families SET is_archived = 1, archived_at = ?,
            archived_by_actor_id = 'actor-1' WHERE family_id = 'family-1'
        """,
        (TIMESTAMP,),
    )


@pytest.mark.parametrize(
    "statement",
    [
        """
        INSERT INTO family_memberships (
            membership_id, family_id, person_id, created_by_actor_id,
            is_active, created_at
        ) VALUES (
            'membership-4', 'family-1', 'person-4', 'actor-1', 1,
            '2026-08-02T10:00:00+00:00'
        )
        """,
        """
        INSERT INTO person_relationships (
            relationship_id, family_id, person_id, related_person_id,
            relationship_type, created_by_actor_id, is_active, created_at
        ) VALUES (
            'relationship-2', 'family-1', 'person-1', 'person-2',
            'guardian', 'actor-1', 1, '2026-08-02T10:00:00+00:00'
        )
        """,
        """
        UPDATE family_memberships SET is_active = 0,
            ended_at = '2026-08-02T10:00:00+00:00', ended_by_actor_id = 'actor-1'
        WHERE membership_id = 'membership-3'
        """,
        "DELETE FROM family_memberships WHERE membership_id = 'membership-3'",
        """
        UPDATE person_relationships SET is_active = 0,
            ended_at = '2026-08-02T10:00:00+00:00', ended_by_actor_id = 'actor-1'
        WHERE relationship_id = 'relationship-1'
        """,
        "DELETE FROM person_relationships WHERE relationship_id = 'relationship-1'",
    ],
)
def test_archived_family_graph_is_read_only_against_repository_bypass(
    tmp_path: Path,
    statement: str,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_archived_family_graph(connection)
        with pytest.raises(sqlite3.IntegrityError, match="archived_family_is_read_only"):
            connection.execute(statement)


def test_v5_migration_preserves_v4_people_and_adds_empty_access_schema(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:4]).migrate()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("person-1", "Ada", None, TIMESTAMP, TIMESTAMP, 1),
        )

    database.migrate()
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
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ACCESS_TABLES
        }
        assert (
            connection.execute(
                "SELECT display_name FROM people WHERE person_id = 'person-1'"
            ).fetchone()[0]
            == "Ada"
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    assert versions == [1, 2, 3, 4, 5, 6, 7, 8]
    assert tables >= ACCESS_TABLES
    assert counts == dict.fromkeys(ACCESS_TABLES, 0)


def test_v5_migration_failure_rolls_back_every_access_table(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    MigrationRunner(database.connect, migrations=PRODUCT_MIGRATIONS[:4]).migrate()
    broken_v5 = PRODUCT_MIGRATIONS[4]
    statements = (*broken_v5.statements[:3], "THIS IS NOT SQL", *broken_v5.statements[3:])

    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")

    runner = MigrationRunner(
        database.connect,
        migrations=(*PRODUCT_MIGRATIONS[:4], type(broken_v5)(version=5, statements=statements)),
    )

    try:
        runner.migrate()
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError("injected migration failure must be reported")

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

    assert versions == [1, 2, 3, 4]
    assert ACCESS_TABLES.isdisjoint(tables)


def test_v5_database_invariants_are_enforced_by_constraints_and_triggers(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "actor-1")
        _insert_actor(connection, "actor-2")
        _insert_person(connection, "person-1")
        _insert_person(connection, "person-2")
        connection.execute(
            """
            INSERT INTO installation_admin_assignments (
                admin_assignment_id, actor_id, assigned_by_actor_id, is_active, assigned_at
            ) VALUES ('admin-1', 'actor-1', 'actor-1', 1, ?)
            """,
            (TIMESTAMP,),
        )
        _insert_owner(
            connection,
            assignment_id="assignment-1",
            actor_id="actor-1",
            person_id="person-1",
        )

        try:
            connection.execute(
                """
                INSERT INTO person_access_assignments (
                    assignment_id, actor_id, person_id, role, scopes_json, consent_event_id,
                    granted_by_actor_id, is_active, granted_at
                ) VALUES (
                    'assignment-duplicate', 'actor-1', 'person-1', 'caregiver', '[]',
                    'consent-assignment-1', 'actor-1', 1, ?
                )
                """,
                (TIMESTAMP,),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("only one active Actor/Person assignment is allowed")

        connection.execute(
            """
            INSERT INTO own_person_links (
                own_person_link_id, actor_id, person_id, is_active, created_at
            ) VALUES ('own-1', 'actor-1', 'person-1', 1, ?)
            """,
            (TIMESTAMP,),
        )
        for link_id, actor_id, person_id in (
            ("own-actor-duplicate", "actor-1", "person-2"),
            ("own-person-duplicate", "actor-2", "person-1"),
            ("own-without-owner", "actor-2", "person-2"),
        ):
            try:
                connection.execute(
                    """
                    INSERT INTO own_person_links (
                        own_person_link_id, actor_id, person_id, is_active, created_at
                    ) VALUES (?, ?, ?, 1, ?)
                    """,
                    (link_id, actor_id, person_id, TIMESTAMP),
                )
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("active own-Person link invariant was bypassed")

        for statement in (
            "UPDATE installation_admin_assignments SET is_active = 0 "
            "WHERE admin_assignment_id = 'admin-1'",
            "UPDATE person_access_assignments SET is_active = 0 "
            "WHERE assignment_id = 'assignment-1'",
            "UPDATE actors SET status = 'disabled', disabled_at = "
            f"'{TIMESTAMP}', disabled_by_actor_id = 'actor-2' WHERE actor_id = 'actor-1'",
        ):
            try:
                connection.execute(statement)
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("last active privilege invariant was bypassed")


def test_consent_and_access_audit_rows_are_append_only(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "actor-1")
        _insert_person(connection, "person-1")
        _insert_owner(
            connection,
            assignment_id="assignment-1",
            actor_id="actor-1",
            person_id="person-1",
        )
        connection.execute(
            """
            INSERT INTO access_audit_events (
                audit_event_id, actor_id, action_code, target_class, target_id,
                outcome, reason_code, created_at
            ) VALUES ('audit-1', 'actor-1', 'assignment.create', 'person', 'person-1',
                      'success', 'owner_grant', ?)
            """,
            (TIMESTAMP,),
        )

        for statement in (
            "UPDATE person_access_consent_history SET reason_code = 'changed'",
            "DELETE FROM person_access_consent_history",
            "UPDATE access_audit_events SET reason_code = 'changed'",
            "DELETE FROM access_audit_events",
        ):
            try:
                connection.execute(statement)
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("append-only row was mutable")


def test_last_owner_and_own_person_link_survive_update_and_delete_bypasses(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "actor-1")
        _insert_person(connection, "person-1")
        _insert_person(connection, "person-2")
        _insert_owner(
            connection,
            assignment_id="assignment-1",
            actor_id="actor-1",
            person_id="person-1",
        )

        with pytest.raises(sqlite3.IntegrityError, match="last_active_person_owner"):
            connection.execute(
                "UPDATE person_access_assignments SET person_id = 'person-2' "
                "WHERE assignment_id = 'assignment-1'"
            )

        connection.execute(
            """
            INSERT INTO own_person_links (
                own_person_link_id, actor_id, person_id, is_active, created_at
            ) VALUES ('own-1', 'actor-1', 'person-1', 1, ?)
            """,
            (TIMESTAMP,),
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="active_own_person_link_requires_owner"
        ):
            connection.execute(
                "DELETE FROM person_access_assignments WHERE assignment_id = 'assignment-1'"
            )


def test_active_relationship_survives_membership_update_and_delete_bypasses(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "actor-1")
        for person_id in ("person-1", "person-2", "person-3"):
            _insert_person(connection, person_id)
        for family_id in ("family-1", "family-2"):
            connection.execute(
                "INSERT INTO families VALUES (?, ?, 'actor-1', ?, 0, NULL, NULL)",
                (family_id, family_id, TIMESTAMP),
            )
        for membership_id, person_id in (
            ("membership-1", "person-1"),
            ("membership-2", "person-2"),
        ):
            connection.execute(
                """
                INSERT INTO family_memberships (
                    membership_id, family_id, person_id, created_by_actor_id,
                    is_active, created_at
                ) VALUES (?, 'family-1', ?, 'actor-1', 1, ?)
                """,
                (membership_id, person_id, TIMESTAMP),
            )
        connection.execute(
            """
            INSERT INTO person_relationships (
                relationship_id, family_id, person_id, related_person_id,
                relationship_type, created_by_actor_id, is_active, created_at
            ) VALUES (
                'relationship-1', 'family-1', 'person-1', 'person-2',
                'parent', 'actor-1', 1, ?
            )
            """,
            (TIMESTAMP,),
        )

        for statement in (
            "UPDATE family_memberships SET family_id = 'family-2' "
            "WHERE membership_id = 'membership-1'",
            "UPDATE family_memberships SET person_id = 'person-3' "
            "WHERE membership_id = 'membership-1'",
            "UPDATE family_memberships SET is_active = 0 "
            "WHERE membership_id = 'membership-1'",
            "DELETE FROM family_memberships WHERE membership_id = 'membership-1'",
        ):
            with pytest.raises(
                sqlite3.IntegrityError, match="active_relationship_requires_membership"
            ):
                connection.execute(statement)


def test_active_admin_assignment_requires_active_actor_on_insert_and_update(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "active-actor")
        connection.execute(
            """
            INSERT INTO actors (
                actor_id, username_normalized, display_name, status, created_at,
                disabled_at, disabled_by_actor_id
            ) VALUES (
                'disabled-actor', 'disabled', 'Disabled', 'disabled', ?, ?, 'active-actor'
            )
            """,
            (TIMESTAMP, TIMESTAMP),
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="active_admin_requires_active_actor"
        ):
            connection.execute(
                """
                INSERT INTO installation_admin_assignments (
                    admin_assignment_id, actor_id, assigned_by_actor_id,
                    is_active, assigned_at
                ) VALUES ('admin-disabled', 'disabled-actor', 'active-actor', 1, ?)
                """,
                (TIMESTAMP,),
            )
        connection.execute(
            """
                INSERT INTO installation_admin_assignments (
                    admin_assignment_id, actor_id, assigned_by_actor_id,
                    is_active, assigned_at, revoked_at, revoked_by_actor_id
                ) VALUES (
                    'admin-disabled', 'disabled-actor', 'active-actor', 0, ?, ?, 'active-actor'
                )
                """,
                (TIMESTAMP, TIMESTAMP),
            )
        with pytest.raises(
            sqlite3.IntegrityError, match="active_admin_requires_active_actor"
        ):
            connection.execute(
                "UPDATE installation_admin_assignments SET is_active = 1, "
                "revoked_at = NULL, revoked_by_actor_id = NULL "
                "WHERE admin_assignment_id = 'admin-disabled'"
            )
        connection.execute(
            """
            INSERT INTO installation_admin_assignments (
                admin_assignment_id, actor_id, assigned_by_actor_id,
                is_active, assigned_at
            ) VALUES ('admin-active', 'active-actor', 'active-actor', 1, ?)
            """,
            (TIMESTAMP,),
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="active_admin_requires_active_actor"
        ):
            connection.execute(
                "UPDATE installation_admin_assignments SET actor_id = 'disabled-actor' "
                "WHERE admin_assignment_id = 'admin-active'"
            )


def test_disabled_actor_admin_assignment_never_counts_as_last_active_admin(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        _insert_actor(connection, "actor-1")
        _insert_actor(connection, "actor-2")
        for assignment_id, actor_id in (("admin-1", "actor-1"), ("admin-2", "actor-2")):
            connection.execute(
                """
                INSERT INTO installation_admin_assignments (
                    admin_assignment_id, actor_id, assigned_by_actor_id,
                    is_active, assigned_at
                ) VALUES (?, ?, 'actor-1', 1, ?)
                """,
                (assignment_id, actor_id, TIMESTAMP),
            )
        connection.execute("DROP TRIGGER actor_disable_requires_privilege_revocation")
        connection.execute(
            """
            UPDATE actors SET status = 'disabled', disabled_at = ?,
                disabled_by_actor_id = 'actor-1' WHERE actor_id = 'actor-2'
            """,
            (TIMESTAMP,),
        )

        with pytest.raises(sqlite3.IntegrityError, match="last_active_installation_admin"):
            connection.execute(
                """
                UPDATE installation_admin_assignments
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = 'actor-1'
                WHERE admin_assignment_id = 'admin-1'
                """,
                (TIMESTAMP,),
            )
