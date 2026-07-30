from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from app.config import ConfigError, load_settings
from app.product_core.installation_backup import (
    BackupReport,
    InstallationBackupError,
    InstallationBackupService,
    verify_installation_backup,
)
from app.product_core.installation_recovery import (
    InstallationRecoveryError,
    InstallationRecoveryService,
    RecoveryReport,
)


class _CliUsageError(Exception):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _CliUsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(prog="python -m app.product_core.backup_cli")
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup")
    backup.add_argument("--database", type=Path)
    backup.add_argument("--source-dir", type=Path)
    backup.add_argument("--destination", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)

    preflight = commands.add_parser("preflight")
    preflight.add_argument("--backup", type=Path, required=True)
    preflight.add_argument("--target-root", type=Path, required=True)

    recover = commands.add_parser("recover")
    recover.add_argument("--backup", type=Path, required=True)
    recover.add_argument("--target-root", type=Path, required=True)
    recover.add_argument("--confirm-maintenance", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except (_CliUsageError, SystemExit):
        _print_usage_failure()
        return 2
    if args.command == "backup":
        return _backup(args.database, args.source_dir, args.destination)
    if args.command == "verify":
        return _verify(args.backup)
    if args.command == "preflight":
        return _preflight(args.backup, args.target_root)
    if args.command == "recover":
        return _recover(args.backup, args.target_root, args.confirm_maintenance)
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


def _preflight(backup_path: Path, target_root: Path) -> int:
    try:
        report = InstallationRecoveryService().preflight(backup_path, target_root)
    except (InstallationRecoveryError, OSError, ValueError) as exc:
        return _print_recovery_failure("preflight", backup_path, target_root, exc)
    return _print_recovery_success("preflight", backup_path, report)


def _recover(backup_path: Path, target_root: Path, confirm_maintenance: bool) -> int:
    try:
        report = InstallationRecoveryService().recover(
            backup_path,
            target_root,
            confirm_maintenance=confirm_maintenance,
        )
    except (InstallationRecoveryError, OSError, ValueError) as exc:
        return _print_recovery_failure("recover", backup_path, target_root, exc)
    return _print_recovery_success("recover", backup_path, report)


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


def _print_recovery_success(operation: str, backup_path: Path, report: RecoveryReport) -> int:
    print(
        json.dumps(
            {
                "backup_path": str(backup_path),
                "operation": operation,
                "product_core_schema_version": report.product_core_schema_version,
                "source_bytes": report.source_bytes,
                "source_count": report.source_count,
                "status": "valid",
                "target_root": str(report.target_root),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _print_recovery_failure(
    operation: str, backup_path: Path, target_root: Path, exc: BaseException
) -> int:
    reason_code = exc.code if isinstance(exc, InstallationRecoveryError) else "recovery_failed"
    payload: dict[str, str] = {
        "backup_path": str(backup_path),
        "operation": operation,
        "reason_code": reason_code,
        "status": "invalid",
        "target_root": str(target_root),
    }
    if isinstance(exc, InstallationRecoveryError) and exc.artifact_path is not None:
        payload["abandoned_artifact_path"] = str(exc.artifact_path)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 1


def _print_usage_failure() -> None:
    print(
        json.dumps(
            {"operation": "cli", "reason_code": "invalid_cli_usage", "status": "invalid"},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _reason_code(exc: BaseException, fallback: str) -> str:
    if isinstance(exc, InstallationBackupError):
        return exc.code
    return fallback


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
