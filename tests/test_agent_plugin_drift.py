"""Deterministic rebuild and build smoke for the Agent Plugins package.

Rebuilds the plugin from canonical sources into a clean temp directory with
``scripts/build_agent_plugin.py`` and asserts byte-equality with the committed
``agent-plugins/opencare-trust/`` tree, then runs the full conformance
validation and the build smoke on the rebuilt tree. The smoke inspects
plugin.json, discovers both skills, validates frontmatter, and verifies the
bundled schema/fixture hashes against the canonical sources. No network, no
client configuration install.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from tests.agent_plugin_common import (
    PLUGIN_DIR,
    ROOT,
    discover_skills,
    package_files,
    parse_frontmatter,
    validate_package,
)

BUILD_SCRIPT = ROOT / "scripts" / "build_agent_plugin.py"
ASSET_NAMES = (
    "trust-envelope.schema.json",
    "execution-receipt.schema.json",
    "authorization-snapshot.schema.json",
    "allowed-envelope.json",
    "allowed-receipt.json",
)


def _rebuild(dest: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--output", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_rebuild_is_byte_identical_to_committed_package(tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    _rebuild(rebuilt)
    committed = package_files(PLUGIN_DIR)
    regenerated = package_files(rebuilt)
    assert {p.relative_to(rebuilt).as_posix() for p in regenerated} == {
        p.relative_to(PLUGIN_DIR).as_posix() for p in committed
    }
    for path in committed:
        rel = path.relative_to(PLUGIN_DIR)
        assert (rebuilt / rel).read_bytes() == path.read_bytes(), f"{rel} drifted"


def test_rebuild_creates_no_symlinks(tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    _rebuild(rebuilt)
    package_files(rebuilt)  # raises on any symlink/junction
    assert not any(p.is_symlink() or p.is_junction() for p in rebuilt.rglob("*"))


def test_build_smoke_from_clean_directory(tmp_path: Path) -> None:
    rebuilt = tmp_path / "smoke"
    _rebuild(rebuilt)

    assert validate_package(rebuilt) == []

    manifest = json.loads((rebuilt / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "opencare-trust"
    assert manifest["$schema"].endswith("/1.0.0/plugin.schema.json")

    skills = discover_skills(rebuilt)
    assert {s.name for s in skills} == {
        "opencare-health-agent",
        "opencare-trust-envelope",
    }
    for skill in skills:
        frontmatter = parse_frontmatter(
            (skill / "SKILL.md").read_text(encoding="utf-8")
        )
        assert frontmatter["name"] == skill.name

    assets = rebuilt / "skills" / "opencare-trust-envelope" / "assets"
    for name in ASSET_NAMES:
        assert (assets / name).is_file()

    for name, source in (
        *[(n, ROOT / "schemas" / "agent-trust" / n) for n in ASSET_NAMES[:3]],
        *[
            (n, ROOT / "fixtures" / "agent-trust" / n)
            for n in ("allowed-envelope.json", "allowed-receipt.json")
        ],
    ):
        assert hashlib.sha256((assets / name).read_bytes()).hexdigest() == (
            hashlib.sha256(source.read_bytes()).hexdigest()
        ), f"{name} hash does not match its canonical source"
