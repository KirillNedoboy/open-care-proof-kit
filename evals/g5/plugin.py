"""Portable plugin package integrity helpers (G5).

Self-contained stdlib tooling for the committed ``agent-plugins/opencare-trust/``
package: a deterministic tree hash (its identity), symlink-rejecting file
enumeration, skill-name discovery, and an integrity check that rebuilds the
package from canonical sources and compares it (modulo checkout line-ending
normalization) to the committed tree.

Reused by the reviewer route (``evals/g5_review``), the client-smoke harness
(``scripts/g5_client_smoke.py``), and the supply-chain tests
(``tests/test_g5_plugin_supply_chain.py``). No network, no client install, no
real health data.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "agent-plugins" / "opencare-trust"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_agent_plugin.py"

REQUIRED_SKILLS = ("opencare-health-agent", "opencare-trust-envelope")


def normalize_bytes(data: bytes) -> bytes:
    """Normalize a checkout's CRLF line endings to LF for canonical comparison."""
    return data.replace(b"\r\n", b"\n")


def package_files(root: Path = PLUGIN_DIR) -> list[tuple[str, bytes]]:
    """Return ``[(relpath, bytes)]`` sorted by relpath; reject symlinks/junctions."""
    files: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise AssertionError(f"package must not contain a symlink/junction: {path}")
        if path.is_file():
            files.append((path.relative_to(root).as_posix(), path.read_bytes()))
    return files


def plugin_tree_hash(root: Path = PLUGIN_DIR) -> str:
    """Deterministic identity hash over the package tree (relpath + content)."""
    digest = hashlib.sha256()
    for relpath, content in package_files(root):
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(content)
        digest.update(b"\x00")
    return digest.hexdigest()


def discover_skill_names(root: Path = PLUGIN_DIR) -> set[str]:
    """Return the set of skill names discovered under ``root/skills/``."""
    skills_root = root / "skills"
    names: set[str] = set()
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        frontmatter = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        name = frontmatter.get("name")
        if name is not None:
            names.add(name)
    return names


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the tiny ``key: value`` frontmatter subset used by the skills."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("frontmatter must start with a `---` delimiter")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"frontmatter line is not `key: value`: {line!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key or key in values:
            raise ValueError(f"invalid or duplicate frontmatter key {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    raise ValueError("frontmatter is not closed with a `---` delimiter")


def _rebuild_to(dest: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--output", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"plugin rebuild failed: {result.stderr}")


def verify_plugin_integrity(
    root: Path = PLUGIN_DIR, tmp_root: Path | None = None
) -> dict[str, Any]:
    """Run the G5 plugin-integrity checks; return a structured result."""
    failures: list[str] = []
    try:
        tree_hash = plugin_tree_hash(root)
    except AssertionError as exc:
        return {"passed": False, "failures": [str(exc)], "tree_hash": None}

    if (root / "mcp.json").exists() or any(rel == "mcp.json" for rel, _ in package_files(root)):
        failures.append("mcp.json must not exist (skill-only package)")

    skill_names = discover_skill_names(root)
    missing = set(REQUIRED_SKILLS) - skill_names
    if missing:
        failures.append(f"missing skills: {sorted(missing)}")
    unexpected = skill_names - set(REQUIRED_SKILLS)
    if unexpected:
        failures.append(f"unexpected skills: {sorted(unexpected)}")

    # Deterministic rebuild must reproduce the committed tree (modulo checkout
    # line-ending normalization; the repo uses autocrlf on Windows).
    rebuilt: dict[str, bytes] = {}
    if tmp_root is not None:
        dest = tmp_root / "rebuilt"
        _rebuild_to(dest)
        for relpath, content in package_files(dest):
            rebuilt[relpath] = normalize_bytes(content)
        committed = {rel: normalize_bytes(data) for rel, data in package_files(root)}
        if set(rebuilt) != set(committed):
            failures.append("rebuilt file set differs from committed package")
        else:
            for relpath in sorted(rebuilt):
                if rebuilt[relpath] != committed[relpath]:
                    failures.append(f"{relpath} drifted from canonical sources")

    return {
        "passed": not failures,
        "failures": failures,
        "tree_hash": tree_hash,
        "skills": sorted(skill_names),
        "no_mcp_json": (root / "mcp.json").exists() is False,
    }

def load_plugin_manifest(root: Path = PLUGIN_DIR) -> dict[str, Any]:
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    return manifest


__all__ = [
    "PLUGIN_DIR",
    "REQUIRED_SKILLS",
    "discover_skill_names",
    "load_plugin_manifest",
    "normalize_bytes",
    "package_files",
    "parse_frontmatter",
    "plugin_tree_hash",
    "verify_plugin_integrity",
]
