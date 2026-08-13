"""Client-smoke harness logic (G5, Phase 4).

Offline, non-destructive tooling that (1) computes the exact tree identity of
the committed ``agent-plugins/opencare-trust/`` package, (2) best-effort
detects known compatible clients and reports versions, (3) prepares a
temporary/reversible install path, (4) machine-checks package discovery and
both skills, and (5) restores state by removing the temp path.

It never installs a full client, enables paid services, signs into an account,
creates a marketplace listing, or drives a GUI. GUI-only steps are returned as
exact manual instructions for a human operator; everything checkable offline is
machine-checked before and after.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evals.g5.plugin import (
    PLUGIN_DIR,
    REQUIRED_SKILLS,
    discover_skill_names,
    package_files,
    plugin_tree_hash,
)

#: Known compatible clients (design doc §7.1/§12.2) and their version probes.
CLIENT_PROBES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cursor", ("Cursor", "cursor")),
    ("vscode", ("code", "code.cmd")),
    ("kiro", ("kiro",)),
)


@dataclass
class ClientDetection:
    name: str
    detected: bool
    version: str | None
    probe: str | None
    notes: str = ""


@dataclass
class TempInstall:
    root: Path
    plugin_dest: Path
    client_name: str
    copied_files: list[str] = field(default_factory=list)


def detect_clients() -> list[ClientDetection]:
    """Best-effort detection of known compatible clients (no install, offline)."""
    detections: list[ClientDetection] = []
    for name, probes in CLIENT_PROBES:
        found = False
        version: str | None = None
        used_probe: str | None = None
        for probe in probes:
            path = shutil.which(probe)
            if path is None:
                continue
            found = True
            used_probe = probe
            version = _probe_version(path)
            break
        detections.append(
            ClientDetection(
                name=name,
                detected=found,
                version=version,
                probe=used_probe,
                notes="" if found else "not found on PATH",
            )
        )
    return detections


def _probe_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    first_line = (result.stdout or result.stderr).splitlines()[0].strip()
    return first_line or None


def prepare_temp_install(client_name: str, base_dir: Path | None = None) -> TempInstall:
    """Copy the package into a temp client plugin location; returns a handle."""
    root = Path(tempfile.mkdtemp(prefix="opencare-g5-client-")) if base_dir is None else base_dir
    root.mkdir(parents=True, exist_ok=True)
    plugin_dest = _plugin_location(root, client_name)
    plugin_dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for relpath, content in package_files(PLUGIN_DIR):
        target = plugin_dest / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        copied.append(relpath)
    return TempInstall(
        root=root, plugin_dest=plugin_dest, client_name=client_name, copied_files=copied
    )


def _plugin_location(root: Path, client_name: str) -> Path:
    if client_name == "cursor":
        return root / "home" / ".cursor" / "plugins" / "local" / "opencare-trust"
    if client_name == "vscode":
        return root / "plugins" / "opencare-trust"
    return root / "plugins" / "local" / "opencare-trust"


def verify_discovery(install: TempInstall) -> dict[str, Any]:
    """Machine-check that the copied package is discoverable and intact."""
    source_hash = plugin_tree_hash()
    dest_hash = _tree_hash_at(install.plugin_dest)
    manifest = install.plugin_dest / "plugin.json"
    skills = discover_skill_names(install.plugin_dest)
    missing = set(REQUIRED_SKILLS) - skills
    return {
        "client": install.client_name,
        "manifest_present": manifest.is_file(),
        "skills": sorted(skills),
        "both_skills_discoverable": not missing,
        "missing_skills": sorted(missing),
        "package_not_rewritten": dest_hash == source_hash,
        "source_tree_hash": source_hash,
        "installed_tree_hash": dest_hash,
    }


def _tree_hash_at(root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for relpath, content in package_files(root):
        digest.update(relpath.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(content)
        digest.update(b"\x00")
    return digest.hexdigest()


def restore(install: TempInstall) -> None:
    """Reversibly remove the temp install path."""
    if install.root.exists():
        shutil.rmtree(install.root, ignore_errors=True)


def manual_smoke_steps(client_name: str) -> list[str]:
    """Exact GUI/manual instructions for the operator (not automatable here)."""
    if client_name == "cursor":
        return [
            "1. Open Cursor.",
            "2. Place the package at ~/.cursor/plugins/local/opencare-trust/ (root plugin.json).",
            "3. Run 'Developer: Reload Window'.",
            "4. Confirm both skills 'opencare-health-agent' and 'opencare-trust-envelope' "
            "appear in the Skills / Customize surface.",
            "5. Record the plugin manifest $schema and both skill names (no rewrite).",
        ]
    if client_name == "vscode":
        return [
            "1. Open VS Code.",
            "2. Set chat.pluginLocations to the directory with the package "
            "(root plugin.json).",
            "3. Reload the window.",
            "4. Confirm both skills 'opencare-health-agent' and 'opencare-trust-envelope' "
            "appear in the agent/skills surface.",
            "5. Record the plugin manifest $schema and both skill names (no rewrite).",
        ]
    return [
        "1. Load the package root plugin.json in the client's local plugin location.",
        "2. Confirm both skills 'opencare-health-agent' and 'opencare-trust-envelope' "
        "are discoverable.",
        "3. Record the plugin manifest $schema and both skill names (no rewrite).",
    ]


__all__ = [
    "CLIENT_PROBES",
    "ClientDetection",
    "TempInstall",
    "detect_clients",
    "manual_smoke_steps",
    "prepare_temp_install",
    "restore",
    "verify_discovery",
]
