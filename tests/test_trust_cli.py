"""CLI contract: existing commands keep working, new export commands are
deterministic, verification exit codes are stable, and the ``opencare-trust``
console entry is declared in ``pyproject.toml``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from app.agent_trust.cli import build_parser, main
from app.agent_trust.fixtures import FIXTURE_NOW

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "fixtures" / "agent-trust"
SCHEMA_FILENAMES = (
    "trust-envelope.schema.json",
    "execution-receipt.schema.json",
    "authorization-snapshot.schema.json",
)
AT = FIXTURE_NOW.isoformat()


def test_console_entry_is_declared_in_pyproject() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["scripts"] == {"opencare-trust": "app.agent_trust.cli:main"}


def test_parser_prog_is_console_name() -> None:
    assert build_parser().prog == "opencare-trust"


def test_existing_cli_commands_still_work(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    envelope_path = tmp_path / "envelope.json"
    assert (
        main(
            [
                "export-envelope",
                "--demo",
                "--person-id",
                "person-alice",
                "--purpose",
                "visit_preparation",
                "--action",
                "summarize_records",
                "--requested-action",
                "Summarize selected records.",
                "--evidence-id",
                "evidence-medication-alice",
                "--tool",
                "context.read",
                "--tool",
                "source.read",
                "--output",
                str(envelope_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["verify-envelope", "--envelope", str(envelope_path)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["inspect-envelope", "--envelope", str(envelope_path)]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["person_id"] == "person-alice"
    assert "credential-alice" not in json.dumps(inspected)


def test_export_schemas_writes_all_three_deterministically(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert main(["export-schemas", "--output", str(first)]) == 0
    assert json.loads(capsys.readouterr().out)["schema_files"] == sorted(SCHEMA_FILENAMES)
    assert main(["export-schemas", "--output", str(second)]) == 0
    for filename in SCHEMA_FILENAMES:
        assert (first / filename).is_file()
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_regenerate_fixtures_is_deterministic(tmp_path: Path) -> None:
    assert main(["regenerate-fixtures", "--output", str(tmp_path)]) == 0
    for filename in (
        "allowed-envelope.json",
        "allowed-receipt.json",
        "refused-before-envelope-receipt.json",
        "unsupported-action-receipt.json",
    ):
        assert (tmp_path / filename).read_bytes() == (FIXTURES_DIR / filename).read_bytes()


def test_verification_exit_codes_are_deterministic(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    envelope = str(FIXTURES_DIR / "allowed-envelope.json")
    assert main(["verify-envelope", "--envelope", envelope, "--at", AT]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "accepted"

    tampered = tmp_path / "tampered-envelope.json"
    tampered.write_bytes(
        (FIXTURES_DIR / "allowed-envelope.json").read_bytes().replace(
            b'"person-alice"', b'"person-mallory"', 1
        )
    )
    assert main(["verify-envelope", "--envelope", str(tampered), "--at", AT]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"

    receipt = str(FIXTURES_DIR / "allowed-receipt.json")
    assert main(
        ["verify-receipt", "--receipt", receipt, "--envelope", envelope, "--at", AT]
    ) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "accepted"

    unsupported = str(FIXTURES_DIR / "unsupported-action-receipt.json")
    assert main(
        ["verify-receipt", "--receipt", unsupported, "--envelope", envelope, "--at", AT]
    ) == 1
    assert "receipt_exceeds_envelope" in json.loads(capsys.readouterr().out)["reason_codes"]


def test_python_dash_m_entry_still_works(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.agent_trust.cli",
            "export-schemas",
            "--output",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "trust-envelope.schema.json").is_file()
