"""Deterministic materialization of the committed Agent Plugins v1 package.

Canonical sources (repo-owned, edited in place) -> ``agent-plugins/opencare-trust/``:

    skills/opencare-health-agent/     health skill: SKILL.md + schemas + docs
    skills/opencare-trust-envelope/   generic trust skill: SKILL.md + references
    schemas/agent-trust/              trust JSON Schemas -> assets/
    fixtures/agent-trust/             synthetic fixtures -> assets/

This script is the only writer of the plugin copy. Rebuilding is a no-op:
identical inputs produce byte-identical output, so the committed package never
drifts from its canonical sources (enforced by ``tests/test_agent_plugin_drift.py``).

Determinism guarantees:

- files are copied byte-for-byte; ``plugin.json`` is serialized from the
  canonical manifest with sorted keys (no timestamps, no machine paths);
- no network access, no Ollama/Sentient state, no generated secrets;
- no symlinks, junctions, or reparse points are ever created;
- paths are handled as POSIX-style relative strings and joined with
  ``pathlib``, so the script behaves identically on Windows and Linux.

Usage:

    python scripts/build_agent_plugin.py [--output DIR]

The default output directory is the repo-owned ``agent-plugins/opencare-trust/``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "agent-plugins" / "opencare-trust"

PLUGIN_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

# Canonical manifest. ``version`` is deliberately omitted: the root
# pyproject.toml version (0.1.0) predates the published Git release history
# (v0.2.0) and must not be reused as a portable-plugin release claim.
# See README.md in the package for the full rationale.
PLUGIN_MANIFEST = {
    "$schema": PLUGIN_SCHEMA_URL,
    "name": "opencare-trust",
    "description": (
        "OpenCare portable trust package: inspect Trust Envelopes and Execution Receipts, "
        "verify provenance, policy, and disclosure fields, and summarize source-backed "
        "health context. Skill-only; verification is never authorization."
    ),
    "repository": "https://github.com/KirillNedoboy/open-care-proof-kit",
    "license": "Apache-2.0",
    "keywords": [
        "opencare",
        "trust",
        "envelope",
        "receipt",
        "health-context",
        "skills",
    ],
}

PLUGIN_README = """# opencare-trust

Portable, skill-only Agent Plugins v1 package for the OpenCare trust contract.

## Contents

- `plugin.json` — strict Agent Plugins 1.0.0 manifest (closed field set;
  `additionalProperties: false`).
- `skills/opencare-trust-envelope/` — generic trust skill: inspect Trust
  Envelopes, verify Execution Receipts, understand provenance / policy /
  disclosure fields, and distinguish verification from current authorization.
  Bundles the three trust JSON Schemas and two synthetic fixtures in `assets/`
  and the field-by-field contract reference in `references/PROTOCOL.md`.
- `skills/opencare-health-agent/` — OpenCare health agent skill: summarizes a
  supplied source-backed context packet, traces claims to sources, and prepares
  clinician questions. Never diagnoses or recommends. Bundles
  `context.schema.json`, `answer.schema.json`, and installation/examples docs.
- `README.md` — this file.

There is deliberately **no `mcp.json`**: the package is skill-only (Agent
Plugins 1.0.0 §6.2 permits a missing MCP location).

## Why there is no `version` field

`plugin.json` intentionally omits `version`. The root `pyproject.toml` version
(`0.1.0`) predates the published Git release history (the project has since
released `v0.2.0`), so reusing it would publish a stale release claim. A
portable plugin version should be minted with the first actual plugin release;
until then the manifest carries no version rather than a wrong one. The root
project version is unchanged.

## Source of truth

| Canonical source | Packaged copy |
| --- | --- |
| health skill `SKILL.md` + schemas | `skills/opencare-health-agent/` |
| health skill docs | `skills/opencare-health-agent/references/` |
| trust skill `SKILL.md` + `references/PROTOCOL.md` | `skills/opencare-trust-envelope/` |
| `schemas/agent-trust/*.schema.json` | `skills/opencare-trust-envelope/assets/` |
| `fixtures/agent-trust/allowed-*.json` | `skills/opencare-trust-envelope/assets/` |

`scripts/build_agent_plugin.py` is the only writer of this package; editing a
skill means editing the canonical file and rerunning the script. A drift test
(`tests/test_agent_plugin_drift.py`) asserts the committed copy stays
byte-identical to the canonical sources. The build is deterministic, offline,
and creates no symlinks.
"""


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _package_files() -> dict[str, bytes]:
    """Return the full package as relative POSIX path -> bytes.

    The map is fixed content, so materialization is deterministic and can
    never escape the plugin root.
    """
    files: dict[str, bytes] = {}

    health = REPO_ROOT / "skills" / "opencare-health-agent"
    for name in ("SKILL.md", "context.schema.json", "answer.schema.json"):
        files[f"skills/opencare-health-agent/{name}"] = _read_bytes(health / name)
    for name in ("README.md", "install.md", "examples.md"):
        files[f"skills/opencare-health-agent/references/{name}"] = _read_bytes(
            health / name
        )

    envelope = REPO_ROOT / "skills" / "opencare-trust-envelope"
    files["skills/opencare-trust-envelope/SKILL.md"] = _read_bytes(envelope / "SKILL.md")
    files["skills/opencare-trust-envelope/references/PROTOCOL.md"] = _read_bytes(
        envelope / "references" / "PROTOCOL.md"
    )

    schemas = REPO_ROOT / "schemas" / "agent-trust"
    for name in (
        "trust-envelope.schema.json",
        "execution-receipt.schema.json",
        "authorization-snapshot.schema.json",
    ):
        files[f"skills/opencare-trust-envelope/assets/{name}"] = _read_bytes(
            schemas / name
        )

    fixtures = REPO_ROOT / "fixtures" / "agent-trust"
    for name in ("allowed-envelope.json", "allowed-receipt.json"):
        files[f"skills/opencare-trust-envelope/assets/{name}"] = _read_bytes(
            fixtures / name
        )

    manifest = json.dumps(PLUGIN_MANIFEST, indent=2, sort_keys=True) + "\n"
    files["plugin.json"] = manifest.encode("utf-8")
    files["README.md"] = PLUGIN_README.encode("utf-8")
    return files


def build(output: Path) -> list[Path]:
    """Materialize the package under ``output``; return the written paths.

    Existing files that are not part of the package are removed so a rebuild
    from a dirty directory is still byte-identical. Symlinks are never created;
    a stray symlink at a target path is replaced by a regular file.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    files = _package_files()

    if output.is_dir():
        for existing in sorted(output.rglob("*")):
            if existing.is_dir():
                continue
            rel = existing.relative_to(output)
            if existing.is_symlink() or rel.as_posix() not in files:
                existing.unlink()
        for directory in sorted(
            (p for p in output.rglob("*") if p.is_dir()), reverse=True
        ):
            with contextlib.suppress(OSError):
                directory.rmdir()

    written: list[Path] = []
    for rel, data in sorted(files.items()):
        target = output.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or not target.exists() or target.read_bytes() != data:
            if target.is_symlink():
                target.unlink()
            target.write_bytes(data)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/build_agent_plugin.py",
        description="Materialize the committed Agent Plugins v1 package "
        "agent-plugins/opencare-trust/ from canonical sources.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/agent-plugins/opencare-trust).",
    )
    args = parser.parse_args(argv)
    output = args.output if args.output is not None else DEFAULT_OUTPUT
    try:
        written = build(output)
    except OSError as exc:
        print(f"error: failed to build plugin at {output}: {exc}", file=sys.stderr)
        return 1
    for path in sorted(written):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
