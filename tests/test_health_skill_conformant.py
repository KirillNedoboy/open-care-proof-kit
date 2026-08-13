"""Canonical health skill conformance and package byte-fidelity.

The canonical skill is ``skills/opencare-health-agent/`` (edited in place with
Agent Skills frontmatter). The packaged copy under
``agent-plugins/opencare-trust/skills/opencare-health-agent/`` must match it
byte-for-byte and must bundle both JSON Schemas.
"""

from __future__ import annotations

import json

from tests.agent_plugin_common import (
    CANONICAL_SKILL_DIR,
    PLUGIN_DIR,
    parse_frontmatter,
)

PACKAGED_SKILL_DIR = PLUGIN_DIR / "skills" / "opencare-health-agent"

# Canonical file -> packaged relative location (docs move to references/).
CANONICAL_FILES = {
    "SKILL.md": "SKILL.md",
    "context.schema.json": "context.schema.json",
    "answer.schema.json": "answer.schema.json",
    "README.md": "references/README.md",
    "install.md": "references/install.md",
    "examples.md": "references/examples.md",
}


def test_canonical_skill_has_valid_frontmatter() -> None:
    text = (CANONICAL_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    assert frontmatter["name"] == "opencare-health-agent"
    assert frontmatter["name"] == CANONICAL_SKILL_DIR.name
    assert 1 <= len(frontmatter["description"]) <= 1024


def test_packaged_copy_matches_canonical_source_byte_for_byte() -> None:
    for canonical_name, packaged_rel in CANONICAL_FILES.items():
        canonical = (CANONICAL_SKILL_DIR / canonical_name).read_bytes()
        packaged = (PACKAGED_SKILL_DIR / packaged_rel).read_bytes()
        assert packaged == canonical, f"{canonical_name} drifted in the package"


def test_packaged_skill_bundles_both_json_schemas() -> None:
    for name in ("context.schema.json", "answer.schema.json"):
        path = PACKAGED_SKILL_DIR / name
        assert path.is_file()
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert isinstance(doc, dict) and doc.get("type") == "object"
