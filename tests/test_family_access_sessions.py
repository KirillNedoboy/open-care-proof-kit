from datetime import UTC, datetime
from pathlib import Path

from app.family_access.sessions import SessionStore


def test_create_session_can_set_active_person_atomically(tmp_path: Path) -> None:
    store = SessionStore(
        tmp_path / "sessions.sqlite3",
        clock=lambda: datetime(2026, 8, 2, 10, tzinfo=UTC),
    )

    created = store.create("actor-1", "credential-1", active_person_id="person-1")

    record = store.resolve(created.session_token)
    assert record is not None
    assert record.active_person_id == "person-1"
