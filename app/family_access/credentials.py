from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
from dataclasses import dataclass

SCRYPT_N = 32_768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SCRYPT_MAXMEM = 67_108_864
PASSWORD_MIN_LENGTH = 12
SALT_BYTES = 16


@dataclass(frozen=True)
class CredentialHash:
    algorithm: str
    algorithm_version: int
    salt: bytes
    verifier: bytes


def normalize_username(username: str) -> str:
    normalized = unicodedata.normalize("NFKC", username).strip().casefold()
    if not normalized:
        raise ValueError("username must not be blank")
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        raise ValueError("username must not contain control characters")
    return normalized


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )


def hash_password(password: str) -> CredentialHash:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    salt = secrets.token_bytes(SALT_BYTES)
    return CredentialHash(
        algorithm="scrypt",
        algorithm_version=1,
        salt=salt,
        verifier=_derive(password, salt),
    )


def verify_password(password: str, credential: CredentialHash) -> bool:
    if credential.algorithm != "scrypt" or credential.algorithm_version != 1:
        return False
    derived = _derive(password, credential.salt)
    return hmac.compare_digest(derived, credential.verifier)


_DUMMY_CREDENTIAL = CredentialHash(
    algorithm="scrypt",
    algorithm_version=1,
    salt=b"opencare-dummy-v1",
    verifier=b"\0" * SCRYPT_DKLEN,
)


def dummy_verify_password(password: str) -> None:
    verify_password(password, _DUMMY_CREDENTIAL)
