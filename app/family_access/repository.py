from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.family_access.models import ActorRecord, AssignmentRecord, InvalidStoredScopes
from app.product_core.models import ensure_utc_datetime


def parse_utc(value: str) -> datetime:
    return ensure_utc_datetime(datetime.fromisoformat(value))


def deserialize_scopes(value: object) -> frozenset[str] | InvalidStoredScopes:
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return InvalidStoredScopes()
    if isinstance(decoded, list) and all(isinstance(scope, str) for scope in decoded):
        return frozenset(decoded)
    return InvalidStoredScopes()


class FamilyAccessRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_actor(self, actor_id: str) -> ActorRecord | None:
        row = self.connection.execute(
            "SELECT actor_id, username_normalized, display_name, status, created_at "
            "FROM actors WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        return None if row is None else self._actor(row)

    def get_actor_by_username(self, username_normalized: str) -> ActorRecord | None:
        row = self.connection.execute(
            "SELECT actor_id, username_normalized, display_name, status, created_at "
            "FROM actors WHERE username_normalized = ?",
            (username_normalized,),
        ).fetchone()
        return None if row is None else self._actor(row)

    def is_active_admin(self, actor_id: str) -> bool:
        return (
            self.connection.execute(
                """
                SELECT 1 FROM installation_admin_assignments ia
                JOIN actors a ON a.actor_id = ia.actor_id
                WHERE ia.actor_id = ? AND ia.is_active = 1 AND a.status = 'active'
                """,
                (actor_id,),
            ).fetchone()
            is not None
        )

    def get_active_assignment(self, actor_id: str, person_id: str) -> AssignmentRecord | None:
        row = self.connection.execute(
            """
            SELECT paa.assignment_id, paa.actor_id, paa.person_id, paa.role,
                   paa.scopes_json, paa.is_active
            FROM person_access_assignments paa
            JOIN actors a ON a.actor_id = paa.actor_id
            JOIN people p ON p.person_id = paa.person_id
            WHERE paa.actor_id = ? AND paa.person_id = ? AND paa.is_active = 1
                  AND a.status = 'active' AND p.is_active = 1
            """,
            (actor_id, person_id),
        ).fetchone()
        if row is None:
            return None
        return AssignmentRecord(
            assignment_id=str(row["assignment_id"]),
            actor_id=str(row["actor_id"]),
            person_id=str(row["person_id"]),
            role=str(row["role"]),  # type: ignore[arg-type]
            scopes=deserialize_scopes(row["scopes_json"]),
            is_active=bool(row["is_active"]),
        )

    @staticmethod
    def _actor(row: sqlite3.Row) -> ActorRecord:
        return ActorRecord(
            actor_id=str(row["actor_id"]),
            username_normalized=str(row["username_normalized"]),
            display_name=str(row["display_name"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            created_at=parse_utc(str(row["created_at"])),
        )
