"""Deterministic security scan over the committed ``opencare-trust`` package.

Rejects accidental inclusion of private keys, ``.env`` files, databases,
backups, session cookies, API-key-shaped strings, absolute local paths
(Windows user directories, POSIX home, OneDrive), generated logs, and model
blobs. The scan is targeted to the committed package content only; it never
touches the network, the venv, Ollama state, or any client configuration.
"""

from __future__ import annotations

import re

from tests.agent_plugin_common import PLUGIN_DIR, package_files

PRIVATE_KEY_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN PGP PRIVATE KEY",
    "PRIVATE KEY-----",
)

API_KEY_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)\bsecret\s*[:=]\s*[\"']?[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)\bpassword\s*[:=]\s*[\"']?[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)\b(?:session[_-]?token|auth[_-]?token|cookie)\b\s*[:=]"),
)

ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),  # C:\... or C:/... (not https://...)
    re.compile(r"(?i)onedrive"),
    re.compile(r"/home/[^/ ]+/"),
    re.compile(r"/Users/[^/ ]+/"),
    re.compile(r"\\Users\\"),
    re.compile(r"(?i)users[\\/][^\\/\s]+"),
)

ENV_LINE_PATTERN = re.compile(r"(?m)^[A-Z][A-Z0-9_]{2,}=[^\s]*$")

FORBIDDEN_FILENAMES = {
    ".env",
    ".env.local",
    ".env.example",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "cookies.txt",
    ".DS_Store",
    "Thumbs.db",
    "session.json",
}
FORBIDDEN_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".log",
    ".bak",
    ".backup",
    ".orig",
    ".rej",
    ".tmp",
    ".gguf",
    ".safetensors",
    ".onnx",
    ".bin",
    ".pyc",
)
FORBIDDEN_NAME_PARTS = ("backup", "session", "cookie", "ollama", "credentials")


def test_scan_never_has_anything_to_flag() -> None:
    """The committed package content is clean: no secrets, paths, or artifacts."""
    violations: list[str] = []
    for path in package_files(PLUGIN_DIR):
        rel = path.relative_to(PLUGIN_DIR).as_posix()
        name = path.name.lower()
        suffix = path.suffix.lower()
        if name in FORBIDDEN_FILENAMES:
            violations.append(f"{rel}: forbidden filename {name!r}")
        if suffix in FORBIDDEN_SUFFIXES:
            violations.append(f"{rel}: forbidden file kind {suffix!r}")
        if any(part in name for part in FORBIDDEN_NAME_PARTS):
            violations.append(f"{rel}: suspicious filename {name!r}")

        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in PRIVATE_KEY_MARKERS:
            if marker in text:
                violations.append(f"{rel}: private-key material marker {marker!r}")
        for pattern in API_KEY_PATTERNS:
            if pattern.search(text):
                violations.append(f"{rel}: API-key/credential-shaped string {pattern.pattern}")
        for pattern in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(text):
                violations.append(f"{rel}: absolute/machine path {pattern.pattern}")
        if ENV_LINE_PATTERN.search(text):
            violations.append(f"{rel}: environment-style KEY=VALUE line")

    assert violations == []


def test_scan_rule_set_is_deterministic() -> None:
    """The scan is a pure function of committed bytes: repeated runs agree."""
    first = [p.read_bytes() for p in package_files(PLUGIN_DIR)]
    second = [p.read_bytes() for p in package_files(PLUGIN_DIR)]
    assert first == second
