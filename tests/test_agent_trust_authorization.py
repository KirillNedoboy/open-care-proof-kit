from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.agent_trust.authorization import OpenCareAuthorizationAdapter
from app.family_access.service import FamilyAccessService
from app.product_core.sqlite import SQLiteDatabase

NOW = datetime(2027, 8, 2, 10, tzinfo=UTC)


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"trust-id-{self.value}"


def test_adapter_captures_live_assignment_consent_and_credential(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    with database.connect() as connection:
        timestamp = NOW.isoformat()
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
            ("person-alice", "Alice", None, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
            ("person-carol", "Carol", None, timestamp, timestamp),
        )
    service = FamilyAccessService(database, clock=lambda: NOW, id_factory=SequenceIds())
    actor = service.bootstrap(
        username="alice",
        display_name="Alice",
        password="correct horse battery",
        person_ids=["person-alice"],
        own_person_id="person-alice",
        confirm_full_owner_access=True,
    )
    with database.connect() as connection:
        credential_id = str(
            connection.execute(
                "SELECT credential_id FROM actor_credentials WHERE actor_id = ?",
                (actor.actor_id,),
            ).fetchone()[0]
        )
        consent_event_id = str(
            connection.execute(
                "SELECT consent_event_id FROM person_access_assignments WHERE actor_id = ?",
                (actor.actor_id,),
            ).fetchone()[0]
        )

    adapter = OpenCareAuthorizationAdapter(service)
    allowed = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-alice",
        required_scopes=frozenset({"person.read", "source.read"}),
        authorized_at=NOW,
    )
    assert allowed.decision == "allow"
    assert allowed.snapshot is not None
    assert allowed.snapshot.consent_event_id == consent_event_id
    assert allowed.snapshot.required_scopes == ["person.read", "source.read"]

    carol = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-carol",
        required_scopes=frozenset({"person.read"}),
        authorized_at=NOW,
    )
    assert carol.decision == "deny"
    assert carol.reason_codes == ["required_scope_missing"]

    service.change_password(actor.actor_id, "correct horse battery", "new correct horse battery")
    revoked = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-alice",
        required_scopes=frozenset({"person.read"}),
        authorized_at=NOW,
    )
    assert revoked.reason_codes == ["authentication_required"]
