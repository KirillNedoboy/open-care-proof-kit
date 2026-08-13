"""Client-smoke harness tests (G5, Phase 4).

These test the harness *logic* (tree identity, detection output format,
temp-path preparation, discovery, restore) with **no real client required** —
the smoke harness itself is offline and never drives a GUI.
"""

from __future__ import annotations

from pathlib import Path

from evals.g5.client_harness import (
    ClientDetection,
    detect_clients,
    manual_smoke_steps,
    prepare_temp_install,
    restore,
    verify_discovery,
)
from evals.g5.plugin import REQUIRED_SKILLS, plugin_tree_hash


def test_tree_identity_is_stable_and_hex() -> None:
    identity = plugin_tree_hash()
    assert identity == plugin_tree_hash()
    assert len(identity) == 64
    assert all(character in "0123456789abcdef" for character in identity)


def test_detect_clients_output_shape() -> None:
    detections = detect_clients()
    assert isinstance(detections, list)
    for detection in detections:
        assert isinstance(detection, ClientDetection)
        assert isinstance(detection.name, str)
        assert isinstance(detection.detected, bool)
        assert detection.version is None or isinstance(detection.version, str)


def test_prepare_temp_install_discovers_both_skills_and_does_not_rewrite(tmp_path: Path) -> None:
    install = prepare_temp_install("cursor", base_dir=tmp_path / "cursor")
    try:
        discovery = verify_discovery(install)
        assert discovery["manifest_present"] is True
        assert set(discovery["skills"]) == set(REQUIRED_SKILLS)
        assert discovery["both_skills_discoverable"] is True
        assert discovery["package_not_rewritten"] is True
        assert discovery["source_tree_hash"] == discovery["installed_tree_hash"]
    finally:
        restore(install)


def test_restore_removes_temp_install(tmp_path: Path) -> None:
    install = prepare_temp_install("vscode", base_dir=tmp_path / "vscode")
    assert install.root.exists()
    restore(install)
    assert not install.root.exists()


def test_manual_steps_cover_each_skill() -> None:
    for client in ("cursor", "vscode", "kiro"):
        steps = manual_smoke_steps(client)
        assert isinstance(steps, list)
        assert steps
        joined = "\n".join(steps)
        assert "opencare-health-agent" in joined
        assert "opencare-trust-envelope" in joined
