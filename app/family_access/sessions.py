from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import stat
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

SESSION_TTL = timedelta(hours=8)
PENDING_EXECUTION_TTL = timedelta(minutes=5)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("session timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("stored session timestamp is invalid")
    return parsed.astimezone(UTC)


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


@dataclass(frozen=True)
class CreatedSession:
    session_token: str
    csrf_token: str
    actor_id: str
    credential_id: str
    expires_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    actor_id: str
    credential_id: str
    active_person_id: str | None
    issued_at: datetime
    expires_at: datetime
@dataclass(frozen=True)
class PendingExecution:
    execution_id: str
    session_id: str
    actor_id: str
    person_id: str
    question_hash: str
    envelope_id: str
    provider_id: str
    provider_hash: str
    state: str
    expires_at: datetime


class SessionStore:
    def __init__(
        self,
        path: Path | str,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(path)
        self.clock = clock
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self._prepare_posix_storage()
        else:
            with suppress(OSError):
                self.path.parent.chmod(0o700)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    session_token_hash BLOB NOT NULL UNIQUE CHECK(length(session_token_hash) = 32),
                    actor_id TEXT NOT NULL,
                    credential_id TEXT NOT NULL,
                    csrf_token_hash BLOB NOT NULL CHECK(length(csrf_token_hash) = 32),
                    active_person_id TEXT,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                )
                """
            )
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if "credential_id" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN credential_id TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_executions (
                    execution_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    question_hash TEXT NOT NULL,
                    envelope_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    provider_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sessions_actor_active_idx "
                "ON sessions(actor_id, revoked_at, expires_at)"
            )
        if os.name == "posix":
            self._verify_posix_permissions()
        else:
            with suppress(OSError):
                self.path.chmod(0o600)

    def _prepare_posix_storage(self) -> None:
        self.path.parent.chmod(0o700)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        os.close(descriptor)
        self.path.chmod(0o600)
        self._verify_posix_permissions()

    def _verify_posix_permissions(self) -> None:
        if stat.S_IMODE(self.path.parent.stat().st_mode) != 0o700:
            raise PermissionError("session directory permissions must be 0700")
        if stat.S_IMODE(self.path.stat().st_mode) != 0o600:
            raise PermissionError("session database permissions must be 0600")

    def create(self, actor_id: str, credential_id: str) -> CreatedSession:
        if not actor_id.strip() or not credential_id.strip():
            raise ValueError("session identity must be non-empty")
        now = self.clock().astimezone(UTC)
        expires_at = now + SESSION_TTL
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_id = secrets.token_hex(16)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, session_token_hash, actor_id, credential_id,
                    csrf_token_hash, active_person_id, issued_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, NULL)
                """,
                (
                    session_id,
                    _token_hash(session_token),
                    actor_id,
                    credential_id,
                    _token_hash(csrf_token),
                    _isoformat(now),
                    _isoformat(expires_at),
                ),
            )
        return CreatedSession(
            session_token=session_token,
            csrf_token=csrf_token,
            actor_id=actor_id,
            credential_id=credential_id,
            expires_at=expires_at,
        )

    def _active_row(self, session_token: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            result = connection.execute(
                "SELECT * FROM sessions WHERE session_token_hash = ? AND revoked_at IS NULL",
                (_token_hash(session_token),),
            ).fetchone()
        row: sqlite3.Row | None = result
        if row is None or _parse_datetime(str(row["expires_at"])) <= self.clock():
            return None
        return row

    def resolve(self, session_token: str) -> SessionRecord | None:
        row = self._active_row(session_token)
        if row is None:
            return None
        credential_id = row["credential_id"]
        if credential_id is None or not str(credential_id).strip():
            self.revoke(session_token)
            return None
        return SessionRecord(
            session_id=str(row["session_id"]),
            actor_id=str(row["actor_id"]),
            credential_id=str(credential_id),
            active_person_id=(
                None if row["active_person_id"] is None else str(row["active_person_id"])
            ),
            issued_at=_parse_datetime(str(row["issued_at"])),
            expires_at=_parse_datetime(str(row["expires_at"])),
        )

    def verify_csrf(self, session_token: str, csrf_token: str) -> bool:
        row = self._active_row(session_token)
        if row is None:
            return False
        return hmac.compare_digest(_token_hash(csrf_token), bytes(row["csrf_token_hash"]))

    def revoke(self, session_token: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions SET revoked_at = ?
                WHERE session_token_hash = ? AND revoked_at IS NULL
                """,
                (_isoformat(self.clock()), _token_hash(session_token)),
            )
        return cursor.rowcount == 1

    def invalidate_actor(self, actor_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE actor_id = ? AND revoked_at IS NULL",
                (_isoformat(self.clock()), actor_id),
            )
        return cursor.rowcount

    def set_active_person(self, session_token: str, person_id: str | None) -> bool:
        if self.resolve(session_token) is None:
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sessions SET active_person_id = ?
                WHERE session_token_hash = ? AND revoked_at IS NULL
                """,
                (person_id, _token_hash(session_token)),
            )
        return cursor.rowcount == 1
    def create_pending(self, *, session_id: str, actor_id: str, person_id: str,
                       question_hash: str, envelope_id: str, provider_id: str,
                       provider_hash: str) -> PendingExecution:
        now = self.clock().astimezone(UTC)
        expires_at = now + PENDING_EXECUTION_TTL
        execution_id = secrets.token_urlsafe(18)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO pending_executions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (execution_id, session_id, actor_id, person_id, question_hash,
                 envelope_id, provider_id, provider_hash, "prepared",
                 _isoformat(now), _isoformat(expires_at)),
            )
        return PendingExecution(execution_id, session_id, actor_id, person_id,
                                question_hash, envelope_id, provider_id, provider_hash,
                                "prepared", expires_at)

    def get_pending(self, execution_id: str) -> PendingExecution | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pending_executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
        if row is None or _parse_datetime(str(row["expires_at"])) <= self.clock():
            return None
        return PendingExecution(*(str(row[key]) for key in (
            "execution_id","session_id","actor_id","person_id","question_hash",
            "envelope_id","provider_id","provider_hash","state"
        )), _parse_datetime(str(row["expires_at"])))

    def consume_pending(self, execution_id: str) -> PendingExecution | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pending_executions WHERE execution_id=? AND state='prepared'",
                (execution_id,),
            ).fetchone()
            if row is None or _parse_datetime(str(row["expires_at"])) <= self.clock():
                return None
            if connection.execute(
                "UPDATE pending_executions SET state='consumed' WHERE execution_id=? AND state='prepared'",
                (execution_id,),
            ).rowcount != 1:
                return None
        return PendingExecution(*(str(row[key]) for key in (
            "execution_id","session_id","actor_id","person_id","question_hash",
            "envelope_id","provider_id","provider_hash","state"
        )), _parse_datetime(str(row["expires_at"])))
