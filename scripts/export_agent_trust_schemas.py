"""Deterministic export of the G4 portable trust JSON Schemas.

Derives the three checked-in schema files
(``schemas/agent-trust/trust-envelope.schema.json``,
``schemas/agent-trust/execution-receipt.schema.json``,
``schemas/agent-trust/authorization-snapshot.schema.json``) from the existing
G1 pydantic contract models. Output is canonical: sorted keys, no timestamps,
no absolute paths. Never hand-author divergent schemas.

Usage:

    python -m scripts.export_agent_trust_schemas [--output DIR]

The default output directory is the repo-owned ``schemas/agent-trust/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent_trust.schemas import (  # noqa: E402
    default_schema_dir,
    write_schemas,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.export_agent_trust_schemas",
        description="Regenerate the checked-in agent-trust JSON Schemas.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/schemas/agent-trust).",
    )
    args = parser.parse_args(argv)
    output = args.output if args.output is not None else default_schema_dir()
    try:
        written = write_schemas(output)
    except OSError as exc:
        print(f"error: failed to write schemas to {output}: {exc}", file=sys.stderr)
        return 1
    for path in sorted(written):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
