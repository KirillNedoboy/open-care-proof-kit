from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.product_core.installation_backup import (
    BACKUP_FORMAT_VERSION,
    PRODUCT_CORE_SCHEMA_VERSION,
    InstallationBackupError,
    _canonical_json,
    _parse_canonical_manifest,
    _read_snapshot,
    _snapshot_sources,
    _validate_snapshot,
    _validated_source_id,
    verify_installation_backup,
)
from app.product_core.models import ensure_utc_datetime, isoformat_utc, parse_utc_datetime

RECOVERY_FORMAT_VERSION = 1
RECOVERY_ARTIFACT_PATTERN = re.compile(
    r"\.opencare-recovery-(?:staging|rollback|failed)-[0-9a-f]{32}\Z"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(UTC)


class InstallationRecoveryError(Exception):
    def __init__(self, code: str, *, artifact_path: Path | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.artifact_path = artifact_path


@dataclass(frozen=True)
class RecoveryReport:
    valid: bool
    target_root: Path
    product_core_schema_version: int
    source_count: int
    source_bytes: int
    database_bytes: int
    database_sha256: str
    backup_manifest_checksum: str


class InstallationRecoveryService:
    def __init__(self, *, clock: Clock = _default_clock) -> None:
        self.clock = clock

    def preflight(self, backup_path: Path | str, target_root: Path | str) -> RecoveryReport:
        backup = _absolute_path(Path(backup_path))
        target = _absolute_path(Path(target_root))
        try:
            backup_report = verify_installation_backup(backup)
            manifest_checksum = _manifest_checksum(backup)
            _validate_target_preflight(backup, target, backup_report.payload_bytes)
            return RecoveryReport(
                valid=True,
                target_root=target,
                product_core_schema_version=backup_report.product_core_schema_version,
                source_count=backup_report.payload_count - 1,
                source_bytes=_source_payload_bytes(backup),
                database_bytes=(backup / "database.sqlite3").stat().st_size,
                database_sha256=_sha256_file(backup / "database.sqlite3"),
                backup_manifest_checksum=manifest_checksum,
            )
        except InstallationRecoveryError:
            raise
        except (InstallationBackupError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise InstallationRecoveryError("preflight_failed") from exc

    def recover(
        self,
        backup_path: Path | str,
        target_root: Path | str,
        *,
        confirm_maintenance: bool,
    ) -> RecoveryReport:
        if not confirm_maintenance:
            raise InstallationRecoveryError("maintenance_confirmation_required")
        backup = _absolute_path(Path(backup_path))
        target = _absolute_path(Path(target_root))
        staging: Path | None = None
        rollback_placeholder: Path | None = None
        activated = False
        target_was_empty = False
        try:
            self.preflight(backup, target)
            manifest = _verified_manifest(backup)
            manifest_checksum = hashlib.sha256(_canonical_json(manifest)).hexdigest()
            staging = _create_private_directory(target.parent, "staging")
            _copy_verified_payloads(backup, manifest, staging)
            _write_recovery_report(staging, manifest_checksum, self.clock(), activation="staged")
            _verify_recovered_installation(staging, activation="staged")
            _set_recovery_report_activation(staging, "activated")

            if _path_exists(target):
                _validate_empty_target(target)
                rollback_placeholder = _private_path(target.parent, "rollback")
                _rename_empty_target_to_placeholder(target, rollback_placeholder)
                target_was_empty = True
            _activate_staging(staging, target)
            staging = None
            activated = True
            _verify_recovered_installation(target, activation="activated")
            _mark_post_activation_verification(target)
            final_report = _verify_recovered_installation(target, activation="activated")
            _verify_backup_manifest_checksum(target, manifest_checksum)
            if rollback_placeholder is not None:
                _remove_directory(rollback_placeholder)
                rollback_placeholder = None
            return final_report
        except BaseException as exc:
            cleanup_code = _recover_failure(
                staging=staging,
                target=target,
                rollback_placeholder=rollback_placeholder,
                activated=activated,
                target_was_empty=target_was_empty,
            )
            if cleanup_code is not None:
                raise InstallationRecoveryError(cleanup_code) from exc
            if isinstance(exc, InstallationRecoveryError):
                raise
            if isinstance(exc, InstallationBackupError):
                raise InstallationRecoveryError(exc.code) from exc
            raise InstallationRecoveryError("recovery_failed") from exc


def verify_recovered_installation(target_root: Path | str) -> RecoveryReport:
    return _verify_recovered_installation(_absolute_path(Path(target_root)), activation="activated")


def _verify_recovered_installation(target: Path, *, activation: str) -> RecoveryReport:
    _validate_recovered_root(target)
    database = target / "database.sqlite3"
    snapshot = _read_snapshot(database)
    try:
        schema_version = _validate_snapshot(snapshot.connection)
        sources = _snapshot_sources(snapshot.connection)
    finally:
        snapshot.connection.close()
    source_bytes = 0
    for source in sources:
        _validated_source_id(source.id)
        relative_path = Path(source.relative_path)
        if (
            relative_path.is_absolute()
            or relative_path.anchor
            or ".." in relative_path.parts
            or not relative_path.parts
        ):
            raise InstallationRecoveryError("source_path_unsafe")
        payload = target / "sources" / source.id / "payload.bin"
        _verify_regular_file(payload, "source_payload_invalid")
        if payload.stat().st_size != source.size_bytes:
            raise InstallationRecoveryError("source_size_mismatch")
        if _sha256_file(payload) != source.content_hash:
            raise InstallationRecoveryError("source_hash_mismatch")
        source_bytes += source.size_bytes
    _validate_recovered_layout(target, {source.id for source in sources})
    report = _read_recovery_report(target / "RECOVERY_REPORT.json")
    backup_manifest_checksum = report["backup_manifest_checksum"]
    assert isinstance(backup_manifest_checksum, str)
    database_size = database.stat().st_size
    database_hash = _sha256_file(database)
    if (
        report["product_core_schema_version"] != schema_version
        or report["restored_database"]
        != {"sha256": database_hash, "size_bytes": database_size}
        or report["source_count"] != len(sources)
        or report["total_source_bytes"] != source_bytes
        or report["target_activation_result"] != activation
    ):
        raise InstallationRecoveryError("recovery_report_inconsistent")
    verification_results = report["verification_results"]
    assert isinstance(verification_results, dict)
    if verification_results.get("staged_installation") != "valid":
        raise InstallationRecoveryError("recovery_report_inconsistent")
    if activation == "staged" and verification_results != {"staged_installation": "valid"}:
        raise InstallationRecoveryError("recovery_report_inconsistent")
    if activation == "activated" and set(verification_results) - {
        "staged_installation",
        "post_activation_installation",
    }:
        raise InstallationRecoveryError("recovery_report_inconsistent")
    return RecoveryReport(
        valid=True,
        target_root=target,
        product_core_schema_version=schema_version,
        source_count=len(sources),
        source_bytes=source_bytes,
        database_bytes=database_size,
        database_sha256=database_hash,
        backup_manifest_checksum=backup_manifest_checksum,
    )


def _validate_target_preflight(backup: Path, target: Path, required_bytes: int) -> None:
    if _paths_overlap(backup, target):
        raise InstallationRecoveryError("backup_target_overlap")
    parent = target.parent
    if not parent.is_dir() or _is_unsafe_link(parent):
        raise InstallationRecoveryError("target_parent_invalid")
    _reject_unsafe_components(parent)
    _reject_unsafe_components(target)
    _reject_abandoned_artifacts(parent)
    if _path_exists(target):
        _validate_empty_target(target)
    try:
        available = shutil.disk_usage(parent).free
    except OSError:
        available = None
    if available is not None and available < required_bytes + 4096:
        raise InstallationRecoveryError("insufficient_space")
    if _path_exists(target) and target.stat().st_dev != parent.stat().st_dev:
        raise InstallationRecoveryError("target_filesystem_mismatch")


def _validate_empty_target(target: Path) -> None:
    if _is_unsafe_link(target):
        raise InstallationRecoveryError("target_link_rejected")
    if not target.is_dir():
        raise InstallationRecoveryError("target_not_directory")
    _reject_unsafe_components(target)
    if any(target.iterdir()):
        raise InstallationRecoveryError("target_not_empty")


def _validated_manifest_sources(manifest: dict[str, object]) -> list[dict[str, object]]:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise InstallationRecoveryError("backup_manifest_invalid")
    result: list[dict[str, object]] = []
    for item in sources:
        if not isinstance(item, dict):
            raise InstallationRecoveryError("backup_manifest_invalid")
        source_id = item.get("source_id")
        if not isinstance(source_id, str):
            raise InstallationRecoveryError("backup_manifest_invalid")
        try:
            _validated_source_id(source_id)
        except InstallationBackupError as exc:
            raise InstallationRecoveryError(exc.code) from exc
        result.append(item)
    return result


def _copy_verified_payloads(backup: Path, manifest: dict[str, object], staging: Path) -> None:
    inventory = manifest.get("payloads")
    if not isinstance(inventory, list):
        raise InstallationRecoveryError("backup_manifest_invalid")
    expected: dict[str, tuple[int, str]] = {}
    for item in inventory:
        if not isinstance(item, dict):
            raise InstallationRecoveryError("backup_manifest_invalid")
        path, size, digest = item.get("path"), item.get("size_bytes"), item.get("sha256")
        if not isinstance(path, str) or not isinstance(size, int) or not isinstance(digest, str):
            raise InstallationRecoveryError("backup_manifest_invalid")
        expected[path] = (size, digest)
    (staging / "sources").mkdir(mode=0o700)
    _copy_file_verified(
        backup / "database.sqlite3",
        staging / "database.sqlite3",
        *expected["database.sqlite3"],
    )
    for source in _validated_manifest_sources(manifest):
        source_id = source["source_id"]
        assert isinstance(source_id, str)
        relative = f"sources/{source_id}/payload.bin"
        destination = staging / "sources" / source_id / "payload.bin"
        destination.parent.mkdir(mode=0o700, parents=True)
        _copy_file_verified(backup / relative, destination, *expected[relative])


def _copy_file_verified(source: Path, destination: Path, size: int, digest: str) -> None:
    _verify_regular_file(source, "backup_payload_missing")
    written = 0
    checksum = hashlib.sha256()
    try:
        with source.open("rb") as input_file, destination.open("xb") as output_file:
            while chunk := input_file.read(1024 * 1024):
                written += len(chunk)
                checksum.update(chunk)
                output_file.write(chunk)
            output_file.flush()
            os.fsync(output_file.fileno())
    except OSError as exc:
        raise InstallationRecoveryError("payload_copy_failed") from exc
    if written != size:
        raise InstallationRecoveryError("payload_size_mismatch")
    if checksum.hexdigest() != digest:
        raise InstallationRecoveryError("payload_hash_mismatch")


def _write_recovery_report(
    staging: Path, manifest_checksum: str, now: datetime, *, activation: str
) -> None:
    database = staging / "database.sqlite3"
    snapshot = _read_snapshot(database)
    try:
        schema_version = _validate_snapshot(snapshot.connection)
        sources = _snapshot_sources(snapshot.connection)
    finally:
        snapshot.connection.close()
    source_bytes = sum(source.size_bytes for source in sources)
    report = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "backup_manifest_checksum": manifest_checksum,
        "operation_timestamp": isoformat_utc(ensure_utc_datetime(now)),
        "product_core_schema_version": schema_version,
        "recovery_format_version": RECOVERY_FORMAT_VERSION,
        "restored_database": {
            "sha256": _sha256_file(database),
            "size_bytes": database.stat().st_size,
        },
        "rollback_result": "not_required",
        "source_count": len(sources),
        "target_activation_result": activation,
        "total_source_bytes": source_bytes,
        "verification_results": {"staged_installation": "valid"},
    }
    with (staging / "RECOVERY_REPORT.json").open("xb") as handle:
        handle.write(_canonical_json(report))
        handle.flush()
        os.fsync(handle.fileno())


def _read_recovery_report(path: Path) -> dict[str, object]:
    _verify_regular_file(path, "recovery_report_missing")
    try:
        raw = path.read_bytes()
        report = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationRecoveryError("recovery_report_invalid") from exc
    if not isinstance(report, dict) or _canonical_json(report) != raw:
        raise InstallationRecoveryError("recovery_report_not_canonical")
    expected_keys = {
        "backup_format_version",
        "backup_manifest_checksum",
        "operation_timestamp",
        "product_core_schema_version",
        "recovery_format_version",
        "restored_database",
        "rollback_result",
        "source_count",
        "target_activation_result",
        "total_source_bytes",
        "verification_results",
    }
    if set(report) != expected_keys:
        raise InstallationRecoveryError("recovery_report_invalid")
    if (
        report["recovery_format_version"] != RECOVERY_FORMAT_VERSION
        or report["backup_format_version"] != BACKUP_FORMAT_VERSION
        or report["product_core_schema_version"] != PRODUCT_CORE_SCHEMA_VERSION
        or not isinstance(report["backup_manifest_checksum"], str)
        or SHA256_PATTERN.fullmatch(report["backup_manifest_checksum"]) is None
        or report["rollback_result"] != "not_required"
        or not isinstance(report["source_count"], int)
        or not isinstance(report["total_source_bytes"], int)
        or not isinstance(report["verification_results"], dict)
    ):
        raise InstallationRecoveryError("recovery_report_invalid")
    restored = report["restored_database"]
    if (
        not isinstance(restored, dict)
        or set(restored) != {"sha256", "size_bytes"}
        or not isinstance(restored["sha256"], str)
        or SHA256_PATTERN.fullmatch(restored["sha256"]) is None
        or not isinstance(restored["size_bytes"], int)
    ):
        raise InstallationRecoveryError("recovery_report_invalid")
    timestamp = report["operation_timestamp"]
    if not isinstance(timestamp, str):
        raise InstallationRecoveryError("recovery_report_invalid")
    try:
        if isoformat_utc(parse_utc_datetime(timestamp)) != timestamp:
            raise InstallationRecoveryError("recovery_report_invalid")
    except ValueError as exc:
        raise InstallationRecoveryError("recovery_report_invalid") from exc
    return report


def _set_recovery_report_activation(staging: Path, activation: str) -> None:
    path = staging / "RECOVERY_REPORT.json"
    report = _read_recovery_report(path)
    report["target_activation_result"] = activation
    _rewrite_recovery_report(path, report)


def _mark_post_activation_verification(target: Path) -> None:
    path = target / "RECOVERY_REPORT.json"
    report = _read_recovery_report(path)
    results = report["verification_results"]
    assert isinstance(results, dict)
    results["post_activation_installation"] = "valid"
    _rewrite_recovery_report(path, report)


def _rewrite_recovery_report(path: Path, report: dict[str, object]) -> None:
    try:
        with path.open("r+b") as handle:
            handle.seek(0)
            handle.write(_canonical_json(report))
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise InstallationRecoveryError("recovery_report_update_failed") from exc


def _validate_recovered_root(target: Path) -> None:
    if not target.is_dir() or _is_unsafe_link(target):
        raise InstallationRecoveryError("recovered_target_invalid")
    _reject_unsafe_components(target)


def _validate_recovered_layout(target: Path, source_ids: set[str]) -> None:
    expected_files = {"database.sqlite3", "RECOVERY_REPORT.json"}
    expected_directories = {"sources"}
    for source_id in source_ids:
        expected_files.add(f"sources/{source_id}/payload.bin")
        expected_directories.add(f"sources/{source_id}")
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in target.rglob("*"):
        relative = path.relative_to(target).as_posix()
        if _is_unsafe_link(path):
            raise InstallationRecoveryError("recovered_link_rejected")
        if path.is_dir():
            actual_directories.add(relative)
        elif path.is_file():
            actual_files.add(relative)
        else:
            raise InstallationRecoveryError("recovered_special_file_rejected")
    if actual_files != expected_files or actual_directories != expected_directories:
        raise InstallationRecoveryError("recovered_layout_invalid")


def _activate_staging(staging: Path, target: Path) -> None:
    if not staging.is_dir() or _is_unsafe_link(staging):
        raise InstallationRecoveryError("staging_missing_before_activation")
    if _path_exists(target):
        raise InstallationRecoveryError("target_appeared_before_activation")
    try:
        os.rename(staging, target)
    except OSError as exc:
        raise InstallationRecoveryError("activation_failed") from exc


def _rename_empty_target_to_placeholder(target: Path, placeholder: Path) -> None:
    if not target.is_dir() or any(target.iterdir()):
        raise InstallationRecoveryError("target_changed_before_activation")
    if _path_exists(placeholder):
        raise InstallationRecoveryError("rollback_placeholder_exists")
    try:
        os.rename(target, placeholder)
    except OSError as exc:
        raise InstallationRecoveryError("target_placeholder_rename_failed") from exc


def _recover_failure(
    *,
    staging: Path | None,
    target: Path,
    rollback_placeholder: Path | None,
    activated: bool,
    target_was_empty: bool,
) -> str | None:
    try:
        if staging is not None and _path_exists(staging):
            _remove_directory(staging)
        if activated and _path_exists(target):
            failed = _private_path(target.parent, "failed")
            if _path_exists(failed):
                return "rollback_failed"
            os.rename(target, failed)
            _remove_directory(failed)
        if (
            target_was_empty
            and rollback_placeholder is not None
            and _path_exists(rollback_placeholder)
        ):
            if _path_exists(target):
                return "rollback_failed"
            os.rename(rollback_placeholder, target)
        return None
    except OSError:
        return "rollback_failed"


def _verify_backup_manifest_checksum(target: Path, expected: str) -> None:
    report = _read_recovery_report(target / "RECOVERY_REPORT.json")
    if report["backup_manifest_checksum"] != expected:
        raise InstallationRecoveryError("recovery_report_manifest_mismatch")


def _verified_manifest(backup: Path) -> dict[str, object]:
    verify_installation_backup(backup)
    try:
        return _parse_canonical_manifest((backup / "manifest.json").read_bytes())
    except InstallationBackupError as exc:
        raise InstallationRecoveryError(exc.code) from exc


def _manifest_checksum(backup: Path) -> str:
    return _sha256_file(backup / "manifest.json")


def _source_payload_bytes(backup: Path) -> int:
    manifest = _verified_manifest(backup)
    sizes: list[int] = []
    for item in _validated_manifest_sources(manifest):
        size = item.get("size_bytes")
        if not isinstance(size, int):
            raise InstallationRecoveryError("backup_manifest_invalid")
        sizes.append(size)
    return sum(sizes)


def _create_private_directory(parent: Path, kind: str) -> Path:
    for _ in range(10):
        path = _private_path(parent, kind)
        try:
            path.mkdir(mode=0o700)
            return path
        except FileExistsError:
            continue
    raise InstallationRecoveryError("private_staging_creation_failed")


def _private_path(parent: Path, kind: str) -> Path:
    return parent / f".opencare-recovery-{kind}-{uuid.uuid4().hex}"


def _reject_abandoned_artifacts(parent: Path) -> None:
    for child in parent.iterdir():
        if RECOVERY_ARTIFACT_PATTERN.fullmatch(child.name) is not None:
            raise InstallationRecoveryError("abandoned_recovery_artifact", artifact_path=child)


def _verify_regular_file(path: Path, code: str) -> None:
    _reject_unsafe_components(path)
    if not path.is_file() or _is_unsafe_link(path):
        raise InstallationRecoveryError(code)


def _reject_unsafe_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if _path_exists(current) and _is_unsafe_link(current):
            raise InstallationRecoveryError("symlink_or_reparse_rejected")


def _is_unsafe_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(reparse and attributes & reparse)


def _absolute_path(path: Path) -> Path:
    if ".." in path.parts:
        raise InstallationRecoveryError("ambiguous_path")
    return Path(os.path.abspath(path))


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _path_exists(path: Path) -> bool:
    return path.exists() or _is_unsafe_link(path)


def _remove_directory(path: Path) -> None:
    if not path.is_dir() or _is_unsafe_link(path):
        raise OSError("unsafe recovery artifact")
    shutil.rmtree(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
