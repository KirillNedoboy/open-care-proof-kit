"""G5 client-smoke harness entry point (offline, reversible).

Usage:

    python scripts/g5_client_smoke.py [--client cursor|vscode|kiro] [--all]

Prints: the exact package tree identity, detected client versions, the result
of a temporary/reversible install + discovery check (both skills, package not
rewritten), and — for the GUI-only steps — exact manual smoke instructions.
It never installs a full client, signs into an account, enables paid services,
or drives a GUI.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from evals.g5.client_harness import (
    detect_clients,
    manual_smoke_steps,
    prepare_temp_install,
    restore,
    verify_discovery,
)
from evals.g5.plugin import PLUGIN_DIR, plugin_tree_hash


def run_smoke(client_names: list[str]) -> dict[str, Any]:
    tree_hash = plugin_tree_hash()
    detections = [det.__dict__ for det in detect_clients()]
    checks: list[dict[str, Any]] = []
    for client_name in client_names:
        install = prepare_temp_install(client_name)
        try:
            discovery = verify_discovery(install)
            checks.append(
                {
                    "client": client_name,
                    **discovery,
                    "manual_steps": manual_smoke_steps(client_name),
                }
            )
        finally:
            restore(install)
    return {
        "package_tree_hash": tree_hash,
        "package_dir": str(PLUGIN_DIR),
        "clients": detections,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/g5_client_smoke.py")
    parser.add_argument("--client", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    clients = args.client
    if args.all:
        clients = ["cursor", "vscode", "kiro"]
    if not clients:
        clients = ["cursor", "vscode"]

    report = run_smoke(clients)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
