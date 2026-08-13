"""Agent Plugins v1 conformance for the committed ``opencare-trust`` package.

Enforces the G4 design doc rules (docs/architecture/
sentient-g4-portable-trust-package.md §11) against the upstream Agent Plugins
1.0.0 and Agent Skills specifications: strict manifest with a closed field
set, immediate-child skill discovery, valid frontmatter and naming, package
containment, no symlinks, no absolute paths, and no executable or download
artifacts.
"""

from __future__ import annotations

import json

from tests.agent_plugin_common import (
    ALLOWED_ROOT_FIELDS,
    FORBIDDEN_ROOT_FIELDS,
    PLUGIN_DIR,
    PLUGIN_NAME_RE,
    PLUGIN_SCHEMA_URL,
    discover_skills,
    package_files,
    parse_frontmatter,
    validate_package,
)


def test_plugin_manifest_is_strict_agent_plugins_1_0_0() -> None:
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == PLUGIN_SCHEMA_URL
    assert set(manifest) <= ALLOWED_ROOT_FIELDS
    assert not (FORBIDDEN_ROOT_FIELDS & set(manifest))
    assert "version" not in manifest


def test_plugin_name_satisfies_constraints() -> None:
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    name = manifest["name"]
    assert isinstance(name, str)
    assert 1 <= len(name) <= 64
    assert PLUGIN_NAME_RE.fullmatch(name)
    assert "--" not in name and ".." not in name
    assert name[0].isalnum() and name[-1].isalnum()


def test_package_is_fully_conformant() -> None:
    assert validate_package(PLUGIN_DIR) == []


def test_no_mcp_json_anywhere_in_package() -> None:
    assert not [p for p in package_files(PLUGIN_DIR) if p.name == "mcp.json"]


def test_skills_are_immediate_children_of_skills_dir() -> None:
    skills_root = PLUGIN_DIR / "skills"
    immediate = {p.name for p in skills_root.iterdir() if p.is_dir()}
    assert immediate == {"opencare-health-agent", "opencare-trust-envelope"}
    expected = {
        skills_root / "opencare-health-agent" / "SKILL.md",
        skills_root / "opencare-trust-envelope" / "SKILL.md",
    }
    assert set(PLUGIN_DIR.rglob("SKILL.md")) == expected


def test_every_immediate_child_has_regular_skill_md() -> None:
    for skill_dir in discover_skills(PLUGIN_DIR):
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file()
        assert not skill_md.is_symlink()


def test_skill_frontmatter_is_valid_and_matches_directory() -> None:
    for skill_dir in discover_skills(PLUGIN_DIR):
        frontmatter = parse_frontmatter(
            (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        )
        assert frontmatter["name"] == skill_dir.name
        assert 1 <= len(frontmatter["description"]) <= 1024


def test_skill_bodies_are_bounded_for_progressive_disclosure() -> None:
    for skill_dir in discover_skills(PLUGIN_DIR):
        body_lines = (skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines()
        assert len(body_lines) < 500
