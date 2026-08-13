"""Supply-chain / package tests over ``agent-plugins/opencare-trust/`` (G5, Phase 5).

A targeted scanner (not a universal malware scanner) plus re-runs of the cheap
G4 checks: deterministic rebuild, bundled schema/fixture hashes, Skill
frontmatter, containment, no mcp.json, and secret/path scanning.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from evals.g5.plugin import (
    PLUGIN_DIR,
    REQUIRED_SKILLS,
    discover_skill_names,
    normalize_bytes,
    package_files,
    parse_frontmatter,
    plugin_tree_hash,
    verify_plugin_integrity,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*[\"']?[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)\b(?:session[_-]?token|auth[_-]?token|cookie)\b\s*[:=]"),
)

_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),
    re.compile(r"(?i)onedrive"),
    re.compile(r"/home/[^/ ]+/"),
    re.compile(r"/Users/[^/ ]+/"),
)


def test_tree_identity_is_deterministic() -> None:
    assert plugin_tree_hash() == plugin_tree_hash()
    assert len(plugin_tree_hash()) == 64


def test_manifest_is_versionless_and_strict() -> None:
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert "version" not in manifest
    assert manifest["name"] == "opencare-trust"
    assert not ({"permissions", "scopes", "trust", "consent", "health", "tools"} & set(manifest))


def test_deterministic_rebuild_matches_committed(tmp_path: Path) -> None:
    result = verify_plugin_integrity(PLUGIN_DIR, tmp_root=tmp_path)
    assert result["passed"], result["failures"]


def test_bundled_schemas_match_canonical() -> None:
    assets = PLUGIN_DIR / "skills" / "opencare-trust-envelope" / "assets"
    canonical = REPO_ROOT / "schemas" / "agent-trust"
    for name in (
        "trust-envelope.schema.json",
        "execution-receipt.schema.json",
        "authorization-snapshot.schema.json",
    ):
        bundled = normalize_bytes((assets / name).read_bytes())
        source = normalize_bytes((canonical / name).read_bytes())
        assert bundled == source, name


def test_bundled_fixtures_match_canonical() -> None:
    assets = PLUGIN_DIR / "skills" / "opencare-trust-envelope" / "assets"
    canonical = REPO_ROOT / "fixtures" / "agent-trust"
    for name in ("allowed-envelope.json", "allowed-receipt.json"):
        assert hashlib.sha256(normalize_bytes((assets / name).read_bytes())).hexdigest() == (
            hashlib.sha256(normalize_bytes((canonical / name).read_bytes())).hexdigest()
        ), name


def test_skill_frontmatter_valid_and_matches_directory() -> None:
    for skill_dir in sorted((PLUGIN_DIR / "skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        frontmatter = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
        assert frontmatter["name"] == skill_dir.name
        assert 1 <= len(frontmatter["description"]) <= 1024


def test_both_skills_discoverable_and_no_mcp_json() -> None:
    assert set(discover_skill_names(PLUGIN_DIR)) == set(REQUIRED_SKILLS)
    assert not any(rel == "mcp.json" for rel, _ in package_files(PLUGIN_DIR))


def test_no_path_traversal_or_symlink_escape() -> None:
    for relpath, _ in package_files(PLUGIN_DIR):
        assert ".." not in relpath.split("/"), relpath
        assert not relpath.startswith("/"), relpath
    # package_files raises if it finds any symlink/junction.
    package_files(PLUGIN_DIR)


def test_no_secrets_or_absolute_paths_in_package() -> None:
    for relpath, content in package_files(PLUGIN_DIR):
        text = content.decode("utf-8", errors="replace")
        for pattern in _SECRET_PATTERNS:
            assert not pattern.search(text), f"{relpath}: {pattern.pattern}"
        for pattern in _PATH_PATTERNS:
            assert not pattern.search(text), f"{relpath}: {pattern.pattern}"
