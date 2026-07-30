from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.config import ConfigError, load_settings
from app.product_core.installation_backup import (
    BackupReport,
    InstallationBackupError,
    InstallationBackupService,
    verify_installation_backup,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.product_core.backup_cli")
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup")
    backup.add_argument("--database", type=Path)
    backup.add_argument("--source-dir", type=Path)
    backup.add_argument("--destination", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.command == "backup":
        return _backup(args.database, args.source_dir, args.destination)
    if args.command == "verify":
        return _verify(args.backup)
    return 2


def _backup(
    database: Path | None,
    source_dir: Path | None,
    destination: Path,
) -> int:
    try:
        if database is None or source_dir is None:
            settings = load_settings()
            database = settings.product_db_path if database is None else database
            source_dir = settings.source_dir if source_dir is None else source_dir
        report = InstallationBackupService(database, source_dir).backup(destination)
    except (ConfigError, InstallationBackupError, OSError, ValueError) as exc:
        return _print_failure("backup", destination, _reason_code(exc, "backup_failed"))
    return _print_success("backup", report.backup_path, report)


def _verify(backup_path: Path) -> int:
    try:
        report = verify_installation_backup(backup_path)
    except (InstallationBackupError, OSError, ValueError) as exc:
        return _print_failure("verify", backup_path, _reason_code(exc, "verify_failed"))
    return _print_success("verify", report.backup_path, report)


def _print_success(operation: str, path: Path, report: BackupReport) -> int:
    payload = {
        "operation": operation,
        "backup_path": str(path),
        "status": "valid",
        "payload_count": report.payload_count,
        "payload_bytes": report.payload_bytes,
        "product_core_schema_version": report.product_core_schema_version,
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


def _print_failure(operation: str, path: Path, reason_code: str) -> int:
    print(
        json.dumps(
            {
                "operation": operation,
                "backup_path": str(path),
                "status": "invalid",
                "reason_code": reason_code,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 1


def _reason_code(exc: BaseException, fallback: str) -> str:
    if isinstance(exc, InstallationBackupError):
        return exc.code
    return fallback


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
