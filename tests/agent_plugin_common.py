"""Shared helpers for the Agent Plugins v1 package tests.

Tiny stdlib-only YAML frontmatter parser plus package validation used by the
conformance, scan, health-skill, and drift tests. There is no YAML runtime
dependency: the parser understands exactly the frontmatter shape the committed
package uses (``key: value`` pairs inside ``---`` fences).
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "agent-plugins" / "opencare-trust"
CANONICAL_SKILL_DIR = ROOT / "skills" / "opencare-health-agent"

PLUGIN_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

# Agent Plugins 1.0.0 §5.2: closed field set.
ALLOWED_ROOT_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
# Fields the task baseline and the G4 design doc explicitly forbid.
FORBIDDEN_ROOT_FIELDS = frozenset(
    {
        "permissions",
        "scopes",
        "trust",
        "consent",
        "health",
        "tools",
        "capabilities",
        "version",
    }
)

# Agent Plugins 1.0.0 §5.5 (schema pattern, minus lookarounds not needed here).
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
# Agent Skills: lowercase alnum + hyphens, no leading/trailing hyphen, no `--`.
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Absolute-path and machine-specific markers scanned in package content.
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]"),  # C:\... or C:/... (not https://...)
    re.compile(r"(?i)onedrive"),
    re.compile(r"/home/[^/ ]+/"),
    re.compile(r"/Users/[^/ ]+/"),
    re.compile(r"\\Users\\"),
)

# Artifact/executable file kinds that must never be packaged.
FORBIDDEN_SUFFIXES = (
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".whl",
    ".pyc",
)


def package_files(root: Path) -> list[Path]:
    """All regular files under ``root``, sorted; rejects symlinks/junctions."""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise AssertionError(f"package must not contain a symlink/junction: {path}")
        if path.is_file():
            files.append(path)
    return files


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the tiny YAML frontmatter subset used by the committed skills."""
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
        if not key:
            raise ValueError(f"empty frontmatter key in {line!r}")
        if key in values:
            raise ValueError(f"duplicate frontmatter key {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    raise ValueError("frontmatter is not closed with a `---` delimiter")


def skill_errors(skill_dir: Path) -> list[str]:
    """Validate one skill directory against the Agent Skills rules."""
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"{skill_dir}: missing regular SKILL.md")
        return errors
    try:
        frontmatter = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except ValueError as exc:
        errors.append(f"{skill_dir}: {exc}")
        return errors
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if name is None:
        errors.append(f"{skill_dir}: frontmatter missing required `name`")
    else:
        if not (1 <= len(name) <= 64):
            errors.append(f"{skill_dir}: name length {len(name)} outside 1-64")
        if not SKILL_NAME_RE.fullmatch(name):
            errors.append(f"{skill_dir}: name {name!r} violates name constraints")
        if name != skill_dir.name:
            errors.append(
                f"{skill_dir}: frontmatter name {name!r} != directory {skill_dir.name!r}"
            )
    if description is None:
        errors.append(f"{skill_dir}: frontmatter missing required `description`")
    elif not (1 <= len(description) <= 1024):
        errors.append(
            f"{skill_dir}: description length {len(description)} outside 1-1024"
        )
    return errors


def discover_skills(root: Path) -> list[Path]:
    """Immediate child skill directories of ``root/skills/`` (no recursion)."""
    skills_root = root / "skills"
    if not skills_root.is_dir():
        raise AssertionError(f"{root}: missing skills/ directory")
    return sorted(
        p
        for p in skills_root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )


def validate_package(root: Path) -> list[str]:
    """Full Agent Plugins/Agent Skills conformance validation of ``root``.

    Returns a list of violations; an empty list means conformant. Used by both
    the committed-package conformance test and the rebuild smoke test.
    """
    errors: list[str] = []

    manifest_path = root / "plugin.json"
    if not manifest_path.is_file():
        return ["plugin.json missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"plugin.json is not valid JSON: {exc}"]
    if not isinstance(manifest, dict):
        return ["plugin.json is not a JSON object"]

    if manifest.get("$schema") != PLUGIN_SCHEMA_URL:
        errors.append("plugin.json $schema is not the canonical 1.0.0 identifier")
    unknown = set(manifest) - ALLOWED_ROOT_FIELDS
    if unknown:
        errors.append(f"plugin.json has unknown root fields: {sorted(unknown)}")
    forbidden = FORBIDDEN_ROOT_FIELDS & set(manifest)
    if forbidden:
        errors.append(f"plugin.json contains forbidden fields: {sorted(forbidden)}")

    name = manifest.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 64):
        errors.append(f"plugin.json name {name!r} fails length 1-64")
    elif not PLUGIN_NAME_RE.fullmatch(name) or "--" in name or ".." in name:
        errors.append(f"plugin.json name {name!r} violates plugin name constraints")

    for field in ("description", "repository", "license"):
        if field in manifest and not isinstance(manifest[field], str):
            errors.append(f"plugin.json {field!r} must be a string")
    if "keywords" in manifest and (
        not isinstance(manifest["keywords"], list)
        or any(not isinstance(k, str) for k in manifest["keywords"])
    ):
        errors.append("plugin.json keywords must be a list of strings")

    if (root / "mcp.json").exists():
        errors.append("mcp.json must not exist (skill-only package)")

    skills_root = root / "skills"
    if not skills_root.is_dir():
        return errors + ["skills/ directory missing"]
    immediate = [p for p in skills_root.iterdir() if p.is_dir()]
    if not immediate:
        return errors + ["skills/ has no immediate child skill directories"]
    for skill_dir in immediate:
        errors.extend(skill_errors(skill_dir))
        for nested in skill_dir.rglob("SKILL.md"):
            if nested.parent != skill_dir:
                errors.append(f"nested SKILL.md discovered at {nested}")
        # Progressive disclosure: reference material at most one level deep.
        for sub in ("references", "assets", "scripts"):
            base = skill_dir / sub
            if base.is_dir() and any(p.is_dir() for p in base.iterdir()):
                errors.append(f"{base}: nested directory below {sub}/")

    resolved_root = root.resolve()
    for path in package_files(root):
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError:
            errors.append(f"path escapes package root: {path}")
        if path.stat().st_mode & stat.S_IXUSR:
            errors.append(f"executable file in package: {path}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"artifact/executable file in package: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(text):
                errors.append(f"absolute path marker in {path}: {pattern.pattern}")
    return errors
