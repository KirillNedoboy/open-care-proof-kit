import hashlib
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config import ConfigError, load_settings
from app.family_access.credentials import (
    SCRYPT_DKLEN,
    SCRYPT_MAXMEM,
    SCRYPT_N,
    SCRYPT_P,
    SCRYPT_R,
    hash_password,
    normalize_username,
    verify_password,
)
from app.family_access.policy import (
    CAREGIVER_BASE_SCOPES,
    CAREGIVER_OPTIONAL_SCOPES,
    OWNER_SCOPES,
    POLICY_VERSION,
    PersonAccessPolicy,
    build_scopes,
)
from app.family_access.sessions import SESSION_TTL, SessionStore


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def test_scrypt_uses_fixed_parameters_unique_salt_and_nfkc_casefold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN, SCRYPT_MAXMEM) == (
        32_768,
        8,
        1,
        64,
        67_108_864,
    )
    calls: list[dict[str, object]] = []

    def fake_scrypt(password: bytes, **kwargs: object) -> bytes:
        calls.append({"password": password, **kwargs})
        return bytes([len(calls)]) * SCRYPT_DKLEN

    monkeypatch.setattr(hashlib, "scrypt", fake_scrypt)

    first = hash_password("correct horse battery")
    second = hash_password("correct horse battery")

    assert normalize_username("  ＡdMiN  ") == "admin"
    assert first.algorithm == second.algorithm == "scrypt"
    assert first.algorithm_version == second.algorithm_version == 1
    assert len(first.salt) >= 16
    assert first.salt != second.salt
    assert len(first.verifier) == len(second.verifier) == 64
    assert calls == [
        {
            "password": b"correct horse battery",
            "salt": first.salt,
            "n": SCRYPT_N,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "dklen": SCRYPT_DKLEN,
            "maxmem": SCRYPT_MAXMEM,
        },
        {
            "password": b"correct horse battery",
            "salt": second.salt,
            "n": SCRYPT_N,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "dklen": SCRYPT_DKLEN,
            "maxmem": SCRYPT_MAXMEM,
        },
    ]


def test_password_minimum_and_constant_time_verification_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="12"):
        hash_password("too-short")

    credential = hash_password("a sufficiently long password")
    compared: list[tuple[bytes, bytes]] = []

    def fake_compare(left: bytes, right: bytes) -> bool:
        compared.append((left, right))
        return left == right

    monkeypatch.setattr("app.family_access.credentials.hmac.compare_digest", fake_compare)

    assert verify_password("a sufficiently long password", credential) is True
    assert verify_password("a different long password", credential) is False
    assert len(compared) == 2
    assert all(len(left) == len(right) == 64 for left, right in compared)


def test_owner_and_caregiver_scope_matrix_is_fixed_and_policy_denies_by_default() -> None:
    assert POLICY_VERSION == "family-access-v1"
    assert {
        "person.read",
        "person.update",
        "source.read",
        "source.write",
        "candidate.read",
        "candidate.review",
        "medication.read",
        "medication.write",
        "timeline.read",
        "visit.read",
        "visit.write",
        "brief.read",
        "brief.write",
        "brief.export",
        "vault.export",
        "relationship.read",
        "relationship.manage",
        "access.read",
        "access.manage",
        "chat.use",
    } == OWNER_SCOPES
    assert {
        "person.read",
        "source.read",
        "candidate.read",
        "medication.read",
        "timeline.read",
        "visit.read",
        "brief.read",
        "relationship.read",
        "chat.use",
    } == CAREGIVER_BASE_SCOPES
    assert {
        "source.write",
        "candidate.review",
        "medication.write",
        "visit.write",
        "brief.write",
        "brief.export",
        "vault.export",
    } == CAREGIVER_OPTIONAL_SCOPES
    assert build_scopes("owner", {"person.read"}) == OWNER_SCOPES
    assert build_scopes("caregiver", {"vault.export"}) == (CAREGIVER_BASE_SCOPES | {"vault.export"})
    with pytest.raises(ValueError):
        build_scopes("caregiver", {"person.update"})

    policy = PersonAccessPolicy()
    assert (
        policy.authorize(
            actor_id="actor-1",
            person_id="person-1",
            required_scope="person.read",
            assignment=None,
        ).allowed
        is False
    )
    assert (
        policy.authorize(
            actor_id="actor-1",
            person_id="person-1",
            required_scope="person.read",
            assignment={
                "actor_id": "actor-1",
                "person_id": "person-1",
                "role": "caregiver",
                "scopes": CAREGIVER_BASE_SCOPES,
                "is_active": True,
            },
            is_installation_admin=True,
            has_family_membership=True,
            has_relationship=True,
            has_own_person_link=True,
        ).allowed
        is True
    )
    assert (
        policy.authorize(
            actor_id="actor-1",
            person_id="person-2",
            required_scope="person.read",
            assignment=None,
            is_installation_admin=True,
            has_family_membership=True,
            has_relationship=True,
            has_own_person_link=True,
        ).allowed
        is False
    )


@pytest.mark.parametrize(
    ("role", "scopes", "required_scope"),
    [
        ("owner", OWNER_SCOPES - {"person.update"}, "access.manage"),
        ("owner", OWNER_SCOPES | {"unknown.scope"}, "person.update"),
        ("caregiver", CAREGIVER_BASE_SCOPES - {"person.read"}, "relationship.manage"),
        ("caregiver", CAREGIVER_BASE_SCOPES | {"access.manage"}, "access.manage"),
        ("caregiver", CAREGIVER_BASE_SCOPES | {"unknown.scope"}, "person.update"),
    ],
)
def test_policy_denies_corrupt_stored_assignment_scopes(
    role: str, scopes: frozenset[str], required_scope: str
) -> None:
    decision = PersonAccessPolicy().authorize(
        actor_id="actor-1",
        person_id="person-1",
        required_scope=required_scope,
        assignment={
            "actor_id": "actor-1",
            "person_id": "person-1",
            "role": role,
            "scopes": scopes,
            "is_active": True,
        },
    )

    assert decision.allowed is False
    assert decision.reason_code == "invalid_assignment_scopes"


def test_policy_denies_non_string_and_unhashable_corrupt_scope_values() -> None:
    decision = PersonAccessPolicy().authorize(
        actor_id="actor-1",
        person_id="person-1",
        required_scope="person.read",
        assignment={
            "actor_id": "actor-1",
            "person_id": "person-1",
            "role": "owner",
            "scopes": ["person.read", {"plaintext": "corrupt"}],
            "is_active": True,
        },
    )

    assert decision.allowed is False
    assert decision.reason_code == "invalid_assignment_scopes"

    object_only_decision = PersonAccessPolicy().authorize(
        actor_id="actor-1",
        person_id="person-1",
        required_scope="person.read",
        assignment={
            "actor_id": "actor-1",
            "person_id": "person-1",
            "role": "owner",
            "scopes": [{}],
            "is_active": True,
        },
    )

    assert object_only_decision.allowed is False
    assert object_only_decision.reason_code == "invalid_assignment_scopes"


def test_session_path_defaults_outside_product_storage_and_rejects_overlap(
    tmp_path: Path,
) -> None:
    settings = load_settings(
        {
            "OPENCARE_PRODUCT_DB_PATH": str(tmp_path / "product" / "db.sqlite3"),
            "OPENCARE_SOURCE_DIR": str(tmp_path / "product" / "sources"),
        }
    )
    assert settings.session_db_path.is_absolute()
    assert settings.session_db_path.parent != settings.product_db_path.parent
    assert "opencare" in settings.session_db_path.parent.name

    for session_path in (
        tmp_path / "product" / "sessions.sqlite3",
        tmp_path / "product" / "sources" / "sessions.sqlite3",
        tmp_path / "sessions" / "sessions.sqlite3",
    ):
        product_path = tmp_path / "sessions" / "product" / "db.sqlite3"
        source_path = tmp_path / "sessions" / "sources"
        if "product" in session_path.parts:
            product_path = tmp_path / "product" / "db.sqlite3"
            source_path = tmp_path / "product" / "sources"
        with pytest.raises(ConfigError, match="OPENCARE_SESSION_DB_PATH"):
            load_settings(
                {
                    "OPENCARE_PRODUCT_DB_PATH": str(product_path),
                    "OPENCARE_SOURCE_DIR": str(source_path),
                    "OPENCARE_SESSION_DB_PATH": str(session_path),
                }
            )


def test_production_session_path_defaults_to_ephemeral_run_storage() -> None:
    settings = load_settings(
        {
            "OPENCARE_ENV": "production",
            "OPENCARE_SECRET_KEY": "x" * 32,
        }
    )

    assert settings.session_db_path.as_posix() == "/run/opencare/sessions.sqlite3"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
def test_posix_session_file_is_restricted_before_sqlite_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / "runtime" / "sessions.sqlite3"
    original_connect = sqlite3.connect
    observed_modes: list[int] = []

    def checked_connect(path: Path | str, *args: object, **kwargs: object) -> sqlite3.Connection:
        file_path = Path(path)
        observed_modes.append(file_path.stat().st_mode & 0o777)
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr("app.family_access.sessions.sqlite3.connect", checked_connect)
    SessionStore(session_path)

    assert observed_modes == [0o600]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
def test_posix_session_chmod_failure_is_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / "runtime" / "sessions.sqlite3"
    original_chmod = Path.chmod

    def fail_file_chmod(path: Path, mode: int, *args: object, **kwargs: object) -> None:
        if path == session_path:
            raise PermissionError("chmod denied")
        original_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fail_file_chmod)

    with pytest.raises(PermissionError, match="chmod denied"):
        SessionStore(session_path)


def test_session_store_hashes_tokens_expires_absolutely_and_invalidates_actor(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 2, 10, tzinfo=UTC)
    clock = MutableClock(now)
    path = tmp_path / "runtime" / "sessions.sqlite3"
    store = SessionStore(path, clock=clock)

    created = store.create("actor-1", "credential-1")
    assert created.expires_at == now + SESSION_TTL == now + timedelta(hours=8)
    resolved = store.resolve(created.session_token)
    assert resolved is not None
    assert resolved.credential_id == "credential-1"
    assert store.verify_csrf(created.session_token, created.csrf_token) is True
    assert store.verify_csrf(created.session_token, "wrong-csrf-token") is False

    database_bytes = path.read_bytes()
    assert created.session_token.encode() not in database_bytes
    assert created.csrf_token.encode() not in database_bytes
    with sqlite3.connect(path) as connection:
        assert [row[1] for row in connection.execute("PRAGMA table_info(sessions)")] == [
            "session_id",
            "session_token_hash",
            "actor_id",
            "credential_id",
            "csrf_token_hash",
            "active_person_id",
            "issued_at",
            "expires_at",
            "revoked_at",
        ]

    clock.value = created.expires_at
    assert store.resolve(created.session_token) is None
    clock.value = now
    second = store.create("actor-1", "credential-1")
    third = store.create("actor-2", "credential-2")
    assert store.invalidate_actor("actor-1") == 2
    assert store.resolve(second.session_token) is None
    assert store.resolve(third.session_token) is not None

    if os.name == "posix":
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert path.stat().st_mode & 0o777 == 0o600


def test_session_store_migrates_legacy_rows_but_treats_null_credential_as_invalid(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 2, 10, tzinfo=UTC)
    path = tmp_path / "runtime" / "sessions.sqlite3"
    path.parent.mkdir(parents=True)
    token = "legacy-session-token"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                session_token_hash BLOB NOT NULL UNIQUE,
                actor_id TEXT NOT NULL,
                csrf_token_hash BLOB NOT NULL,
                active_person_id TEXT,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO sessions VALUES (?, ?, ?, ?, NULL, ?, ?, NULL)
            """,
            (
                "legacy-session",
                hashlib.sha256(token.encode()).digest(),
                "actor-1",
                hashlib.sha256(b"legacy-csrf").digest(),
                now.isoformat(),
                (now + timedelta(hours=1)).isoformat(),
            ),
        )

    store = SessionStore(path, clock=lambda: now)

    with sqlite3.connect(path) as connection:
        credential_column = connection.execute(
            "SELECT name FROM pragma_table_info('sessions') WHERE name = 'credential_id'"
        ).fetchone()
    assert credential_column is not None
    assert store.resolve(token) is None
