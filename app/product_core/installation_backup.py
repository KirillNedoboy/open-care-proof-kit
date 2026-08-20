from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.family_access.policy import valid_role_scopes
from app.product_core.errors import VisitBriefIntegrityError
from app.product_core.migrations import PRODUCT_MIGRATIONS
from app.product_core.models import (
    PersistedVisitBriefRevision,
    Source,
    ensure_utc_datetime,
    isoformat_utc,
    parse_utc_datetime,
)
from app.product_core.persisted_visit_briefs import verify_persisted_visit_brief_revision

BACKUP_FORMAT_VERSION = 1
PRODUCT_CORE_SCHEMA_VERSION = PRODUCT_MIGRATIONS[-1].version
SOURCE_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
MANIFEST_SHA256_PATTERN = re.compile(rb"[0-9a-f]{64}\n")
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(UTC)


class InstallationBackupError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BackupReport:
    valid: bool
    backup_path: Path
    product_core_schema_version: int
    payload_count: int
    payload_bytes: int


class InstallationBackupService:
    def __init__(
        self,
        database_path: Path | str,
        source_dir: Path | str,
        *,
        clock: Clock = _default_clock,
    ) -> None:
        self.database_path = Path(database_path)
        self.source_dir = Path(source_dir)
        self.clock = clock

    def backup(self, destination: Path | str) -> BackupReport:
        final_destination = Path(destination)
        staging: Path | None = None
        snapshot: _SnapshotConnection | None = None
        try:
            _validate_active_inputs(self.database_path, self.source_dir, final_destination)
            staging = _create_staging_directory(final_destination.parent)
            database_snapshot = staging / "database.sqlite3"
            _create_sqlite_snapshot(self.database_path, database_snapshot)
            snapshot = _read_snapshot(database_snapshot)
            snapshot_schema_version = _validate_snapshot(snapshot.connection)
            sources = _snapshot_sources(snapshot.connection)
            source_root = staging / "sources"
            source_root.mkdir(mode=0o700)
            source_inventory: list[dict[str, object]] = []
            for source in sources:
                _copy_verified_source(self.source_dir, source, source_root)
                source_inventory.append(
                    {
                        "source_id": source.id,
                        "source_type": source.source_type,
                        "media_type": source.media_type,
                        "content_hash": source.content_hash,
                        "size_bytes": source.size_bytes,
                        "path": _source_payload_relative_path(source.id),
                    }
                )
            snapshot.connection.close()
            snapshot = None

            created_at = isoformat_utc(ensure_utc_datetime(self.clock()))
            payloads = _payload_inventory(staging)
            manifest = {
                "format_version": BACKUP_FORMAT_VERSION,
                "product_core_schema_version": snapshot_schema_version,
                "created_at": created_at,
                "snapshot": {"method": "sqlite3.Connection.backup"},
                "sources": source_inventory,
                "payloads": payloads,
            }
            version = _application_version()
            if version is not None:
                manifest["application_version"] = version
            _write_manifest(staging, manifest)
            staged_report = verify_installation_backup(staging, require_complete=False)
            _create_complete_marker(staging)
            if _path_exists(final_destination):
                raise InstallationBackupError("destination_appeared")
            os.rename(staging, final_destination)
            staging = None
            return BackupReport(
                valid=True,
                backup_path=final_destination,
                product_core_schema_version=staged_report.product_core_schema_version,
                payload_count=staged_report.payload_count,
                payload_bytes=staged_report.payload_bytes,
            )
        except BaseException as exc:
            if snapshot is not None:
                snapshot.connection.close()
            cleanup_error = _cleanup_staging(staging)
            if cleanup_error is not None:
                raise InstallationBackupError("staging_cleanup_failed") from cleanup_error
            if isinstance(exc, InstallationBackupError):
                raise
            raise InstallationBackupError("backup_failed") from exc

    def verify(self, backup_path: Path | str) -> BackupReport:
        return verify_installation_backup(Path(backup_path))


@dataclass
class _SnapshotConnection:
    connection: sqlite3.Connection


def verify_installation_backup(
    backup_path: Path | str,
    *,
    require_complete: bool = True,
) -> BackupReport:
    artifact = Path(backup_path)
    try:
        _validate_artifact_root(artifact)
        manifest_bytes = _read_regular_file(artifact / "manifest.json")
        manifest = _parse_canonical_manifest(manifest_bytes)
        _verify_manifest_checksum(artifact, manifest_bytes)
        _validate_manifest_shape(manifest)
        _validate_artifact_layout(artifact, manifest, require_complete=require_complete)
        _verify_payload_inventory(artifact, manifest)
        snapshot = _read_snapshot(artifact / "database.sqlite3")
        try:
            schema_version = _validate_snapshot(snapshot.connection)
            sources = _snapshot_sources(snapshot.connection)
            _verify_source_inventory(manifest, sources)
        finally:
            snapshot.connection.close()
        payloads = manifest["payloads"]
        assert isinstance(payloads, list)
        return BackupReport(
            valid=True,
            backup_path=artifact,
            product_core_schema_version=schema_version,
            payload_count=len(payloads),
            payload_bytes=sum(_payload_size(item) for item in payloads),
        )
    except InstallationBackupError:
        raise
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise InstallationBackupError("backup_verification_failed") from exc


def _validate_active_inputs(database: Path, source_dir: Path, destination: Path) -> None:
    if not database.is_file() or database.is_symlink():
        raise InstallationBackupError("active_database_invalid")
    if not source_dir.is_dir() or source_dir.is_symlink():
        raise InstallationBackupError("active_source_directory_invalid")
    _reject_symlink_components(database)
    _reject_symlink_components(source_dir)
    _ensure_safe_parent(destination.parent)
    if _path_exists(destination):
        raise InstallationBackupError("destination_exists")


def _ensure_safe_parent(parent: Path) -> None:
    parent.mkdir(parents=True, exist_ok=True)
    if not parent.is_dir() or parent.is_symlink():
        raise InstallationBackupError("destination_parent_invalid")
    _reject_symlink_components(parent)


def _create_staging_directory(parent: Path) -> Path:
    staging = Path(tempfile.mkdtemp(prefix=".opencare-backup-", dir=parent))
    with suppress(OSError):
        os.chmod(staging, 0o700)
    return staging


def _create_sqlite_snapshot(active_database: Path, destination: Path) -> None:
    source = sqlite3.connect(_sqlite_uri(active_database), uri=True)
    target = sqlite3.connect(destination)
    try:
        source.execute("PRAGMA query_only=ON")
        source.backup(target)
    finally:
        target.close()
        source.close()


def _read_snapshot(path: Path) -> _SnapshotConnection:
    if not path.is_file() or path.is_symlink():
        raise InstallationBackupError("snapshot_missing")
    connection = sqlite3.connect(_sqlite_uri(path), uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return _SnapshotConnection(connection)


def _validate_snapshot(connection: sqlite3.Connection) -> int:
    integrity_rows = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    if integrity_rows != ["ok"]:
        raise InstallationBackupError("sqlite_integrity_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise InstallationBackupError("sqlite_foreign_key_failed")
    versions = [
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version ASC")
    ]
    expected_versions = [migration.version for migration in PRODUCT_MIGRATIONS]
    if versions != expected_versions:
        raise InstallationBackupError("unsupported_schema_version")
    if versions[-1] != PRODUCT_CORE_SCHEMA_VERSION:
        raise InstallationBackupError("unsupported_schema_version")
    _validate_lifecycle(connection)
    _validate_brief_revisions(connection)
    _validate_documents(connection)
    _validate_family_access(connection)
    _validate_security_evidence(connection)
    return versions[-1]


def _snapshot_sources(connection: sqlite3.Connection) -> list[Source]:
    rows = connection.execute("SELECT * FROM sources ORDER BY id ASC").fetchall()
    sources: list[Source] = []
    for row in rows:
        source = Source(
            id=row["id"],
            person_id=row["person_id"],
            source_type=row["source_type"],
            relative_path=row["relative_path"],
            content_hash=row["content_hash"],
            size_bytes=row["size_bytes"],
            media_type=row["media_type"],
            created_at=parse_utc_datetime(row["created_at"]),
            provenance=json.loads(row["provenance_json"]),
            original_filename=row["original_filename"],
            document_kind=row["document_kind"],
        )
        _validated_source_id(source.id)
        sources.append(source)
    return sources


def _copy_verified_source(source_dir: Path, source: Source, backup_sources: Path) -> Path:
    source_path = _active_source_payload_path(source_dir, source)
    destination = backup_sources / source.id / "payload.bin"
    destination.parent.mkdir(mode=0o700)
    written = 0
    digest = hashlib.sha256()
    try:
        with source_path.open("rb") as input_file, destination.open("xb") as output_file:
            while chunk := input_file.read(1024 * 1024):
                written += len(chunk)
                digest.update(chunk)
                output_file.write(chunk)
            output_file.flush()
            os.fsync(output_file.fileno())
    except OSError as exc:
        raise InstallationBackupError("source_copy_failed") from exc
    if written != source.size_bytes:
        raise InstallationBackupError("source_size_mismatch")
    if digest.hexdigest() != source.content_hash:
        raise InstallationBackupError("source_hash_mismatch")
    return destination


def _active_source_payload_path(source_dir: Path, source: Source) -> Path:
    _validated_source_id(source.id)
    relative = Path(source.relative_path)
    if relative.is_absolute() or relative.anchor or ".." in relative.parts:
        raise InstallationBackupError("source_path_unsafe")
    path = source_dir.joinpath(relative)
    _reject_symlink_components(path)
    if not path.is_file() or path.is_symlink():
        raise InstallationBackupError("source_not_regular_file")
    try:
        path.relative_to(source_dir)
    except ValueError as exc:
        raise InstallationBackupError("source_path_unsafe") from exc
    return path


def _write_manifest(staging: Path, manifest: dict[str, object]) -> None:
    raw = _canonical_json(manifest)
    manifest_path = staging / "manifest.json"
    with manifest_path.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    with (staging / "manifest.sha256").open("xb") as output:
        output.write(hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n")
        output.flush()
        os.fsync(output.fileno())


def _create_complete_marker(staging: Path) -> None:
    with (staging / "COMPLETE").open("xb"):
        pass


def _payload_inventory(staging: Path) -> list[dict[str, object]]:
    paths = [staging / "database.sqlite3"]
    paths.extend(sorted((staging / "sources").glob("*/payload.bin")))
    return [
        {
            "path": path.relative_to(staging).as_posix(),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
    ]


def _verify_manifest_checksum(artifact: Path, manifest_bytes: bytes) -> None:
    checksum = _read_regular_file(artifact / "manifest.sha256")
    if MANIFEST_SHA256_PATTERN.fullmatch(checksum) is None:
        raise InstallationBackupError("manifest_checksum_format_invalid")
    if checksum[:-1].decode("ascii") != hashlib.sha256(manifest_bytes).hexdigest():
        raise InstallationBackupError("manifest_checksum_mismatch")


def _parse_canonical_manifest(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationBackupError("manifest_invalid") from exc
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise InstallationBackupError("manifest_not_canonical")
    return value


def _validate_manifest_shape(manifest: dict[str, object]) -> None:
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise InstallationBackupError("backup_format_unsupported")
    if manifest.get("product_core_schema_version") != PRODUCT_CORE_SCHEMA_VERSION:
        raise InstallationBackupError("unsupported_schema_version")
    if manifest.get("snapshot") != {"method": "sqlite3.Connection.backup"}:
        raise InstallationBackupError("snapshot_metadata_invalid")
    if not isinstance(manifest.get("created_at"), str):
        raise InstallationBackupError("manifest_invalid")
    created_at = manifest["created_at"]
    assert isinstance(created_at, str)
    try:
        if isoformat_utc(parse_utc_datetime(created_at)) != created_at:
            raise InstallationBackupError("manifest_invalid")
    except ValueError as exc:
        raise InstallationBackupError("manifest_invalid") from exc
    if not isinstance(manifest.get("payloads"), list) or not isinstance(
        manifest.get("sources"), list
    ):
        raise InstallationBackupError("manifest_invalid")


def _validate_artifact_root(artifact: Path) -> None:
    if not artifact.is_dir() or artifact.is_symlink():
        raise InstallationBackupError("backup_directory_invalid")
    _reject_symlink_components(artifact)


def _validate_artifact_layout(
    artifact: Path, manifest: dict[str, object], *, require_complete: bool
) -> None:
    payloads = manifest["payloads"]
    assert isinstance(payloads, list)
    expected_files = {"manifest.json", "manifest.sha256"}
    if require_complete:
        complete = artifact / "COMPLETE"
        if not complete.is_file() or complete.is_symlink() or complete.stat().st_size != 0:
            raise InstallationBackupError("backup_incomplete")
        expected_files.add("COMPLETE")
    elif _path_exists(artifact / "COMPLETE"):
        raise InstallationBackupError("backup_marker_premature")
    expected_files.update(_payload_path(item) for item in payloads)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in artifact.rglob("*"):
        relative = path.relative_to(artifact).as_posix()
        if path.is_symlink():
            raise InstallationBackupError("backup_symlink_rejected")
        if path.is_dir():
            actual_directories.add(relative)
        elif path.is_file():
            actual_files.add(relative)
        else:
            raise InstallationBackupError("backup_special_file_rejected")
    expected_directories = {"sources"}
    expected_directories.update(
        str(Path(_payload_path(item)).parent).replace("\\", "/")
        for item in payloads
        if _payload_path(item).startswith("sources/")
    )
    if actual_files != expected_files or actual_directories != expected_directories:
        raise InstallationBackupError("backup_layout_invalid")


def _verify_payload_inventory(artifact: Path, manifest: dict[str, object]) -> None:
    payloads = manifest["payloads"]
    assert isinstance(payloads, list)
    paths = [_payload_path(item) for item in payloads]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise InstallationBackupError("payload_inventory_invalid")
    for item in payloads:
        path = artifact / _payload_path(item)
        if not path.is_file() or path.is_symlink():
            raise InstallationBackupError("payload_missing")
        if path.stat().st_size != _payload_size(item):
            raise InstallationBackupError("payload_size_mismatch")
        if _sha256_file(path) != _payload_hash(item):
            raise InstallationBackupError("payload_hash_mismatch")


def _verify_source_inventory(manifest: dict[str, object], sources: list[Source]) -> None:
    inventory = manifest["sources"]
    assert isinstance(inventory, list)
    expected = [
        {
            "source_id": source.id,
            "source_type": source.source_type,
            "media_type": source.media_type,
            "content_hash": source.content_hash,
            "size_bytes": source.size_bytes,
            "path": _source_payload_relative_path(source.id),
        }
        for source in sources
    ]
    if inventory != expected:
        raise InstallationBackupError("source_inventory_mismatch")


def _validate_lifecycle(connection: sqlite3.Connection) -> None:
    queries = (
        """
        SELECT 1 FROM candidate_facts AS candidate
        JOIN sources AS source ON source.id = candidate.source_id
        WHERE candidate.person_id <> source.person_id LIMIT 1
        """,
        """
        SELECT 1 FROM candidate_facts AS candidate
        JOIN candidate_facts AS predecessor
          ON predecessor.id = candidate.predecessor_candidate_id
        WHERE candidate.predecessor_candidate_id IS NOT NULL
          AND predecessor.person_id <> candidate.person_id LIMIT 1
        """,
        """
        SELECT 1 FROM candidate_facts AS candidate
        WHERE candidate.provenance_locator_json IS NOT NULL
          AND json_valid(candidate.provenance_locator_json) <> 1 LIMIT 1
        """,
        """
        SELECT 1 FROM candidate_facts AS candidate
        JOIN sources AS source ON source.id = candidate.source_id
        WHERE candidate.provenance_locator_json LIKE '%"kind":"span"%'
          AND (
              json_extract(candidate.provenance_locator_json, '$.start') < 0
              OR json_extract(candidate.provenance_locator_json, '$.end')
                 <= json_extract(candidate.provenance_locator_json, '$.start')
              OR json_extract(candidate.provenance_locator_json, '$.end') > source.size_bytes
          )
        LIMIT 1
        """,
        """
        SELECT 1 FROM canonical_records AS record
        JOIN candidate_facts AS candidate ON candidate.id = record.candidate_id
        JOIN sources AS source ON source.id = record.source_id
        WHERE record.person_id <> candidate.person_id
           OR record.person_id <> source.person_id
           OR candidate.status <> 'confirmed' LIMIT 1
        """,
        """
        SELECT 1 FROM canonical_records AS record
        JOIN canonical_records AS replacement
          ON replacement.id = record.superseded_by_record_id
        WHERE record.superseded_by_record_id IS NOT NULL
          AND (
              replacement.person_id <> record.person_id
              OR replacement.fact_type <> record.fact_type
          )
        LIMIT 1
        """,
        """
        SELECT 1 FROM candidate_facts AS candidate
        WHERE candidate.status = 'confirmed'
          AND NOT EXISTS (
              SELECT 1 FROM canonical_records AS record
              WHERE record.candidate_id = candidate.id
          ) LIMIT 1
        """,
        """
        SELECT 1 FROM canonical_records AS record
        WHERE record.is_active = 0 AND record.superseded_by_record_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM timeline_events AS event
        JOIN canonical_records AS record ON record.id = event.canonical_record_id
        JOIN sources AS source ON source.id = event.source_id
        WHERE event.person_id <> record.person_id OR event.person_id <> source.person_id LIMIT 1
        """,
        """
        SELECT 1 FROM visit_briefs AS brief
        LEFT JOIN visit_brief_revisions AS revision
          ON revision.revision_id = brief.current_revision_id
        WHERE brief.current_revision_id IS NOT NULL
          AND (revision.revision_id IS NULL OR revision.brief_id <> brief.brief_id) LIMIT 1
        """,
        """
        SELECT 1 FROM visit_brief_revisions AS revision
        JOIN visit_brief_revisions AS parent ON parent.revision_id = revision.parent_revision_id
        WHERE revision.parent_revision_id IS NOT NULL
          AND parent.brief_id <> revision.brief_id
        LIMIT 1
        """,
        """
        SELECT 1 FROM visit_brief_evidence_selections AS selection
        JOIN visit_brief_revisions AS revision ON revision.revision_id = selection.revision_id
        JOIN visit_briefs AS brief ON brief.brief_id = revision.brief_id
        JOIN visits AS visit ON visit.visit_id = brief.visit_id
        JOIN canonical_records AS record ON record.id = selection.canonical_record_id
        JOIN sources AS source ON source.id = selection.source_id
        WHERE visit.person_id <> record.person_id OR visit.person_id <> source.person_id LIMIT 1
        """,
    )
    for query in queries:
        if connection.execute(query).fetchone() is not None:
            raise InstallationBackupError("lifecycle_consistency_failed")
    visits = connection.execute("SELECT visit_id FROM visits ORDER BY visit_id").fetchall()
    for visit in visits:
        positions = [
            row[0]
            for row in connection.execute(
                "SELECT position FROM visit_questions WHERE visit_id = ? ORDER BY position",
                (visit[0],),
            )
        ]
        if positions != list(range(len(positions))):
            raise InstallationBackupError("lifecycle_consistency_failed")


def _validate_brief_revisions(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT * FROM visit_brief_revisions ORDER BY revision_id").fetchall()
    for row in rows:
        try:
            revision = PersistedVisitBriefRevision(
                revision_id=row["revision_id"],
                brief_id=row["brief_id"],
                revision_number=row["revision_number"],
                origin=row["origin"],
                parent_revision_id=row["parent_revision_id"],
                content_schema_version=row["content_schema_version"],
                render_version=row["render_version"],
                content=json.loads(row["content_json"]),
                rendered_markdown=row["rendered_markdown"],
                content_hash=row["content_hash"],
                created_at=parse_utc_datetime(row["created_at"]),
            )
            verify_persisted_visit_brief_revision(revision)
        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
            VisitBriefIntegrityError,
        ) as exc:
            raise InstallationBackupError("visit_brief_integrity_failed") from exc


def _validate_documents(connection: sqlite3.Connection) -> None:
    invalid_identity = connection.execute(
        """
        SELECT 1
        FROM document_extractions AS extraction
        LEFT JOIN sources AS source ON source.id = extraction.source_id
        WHERE source.id IS NULL
           OR source.source_type <> 'document'
           OR source.person_id <> extraction.person_id
        LIMIT 1
        """
    ).fetchone()
    missing_extraction = connection.execute(
        """
        SELECT 1 FROM sources AS source
        WHERE source.source_type = 'document'
          AND NOT EXISTS (
              SELECT 1 FROM document_extractions AS extraction
              WHERE extraction.source_id = source.id
                AND extraction.person_id = source.person_id
                AND extraction.status = 'complete'
          )
        LIMIT 1
        """
    ).fetchone()
    if invalid_identity is not None or missing_extraction is not None:
        raise InstallationBackupError("document_extraction_consistency_failed")

    extractions = connection.execute(
        "SELECT * FROM document_extractions ORDER BY extraction_id"
    ).fetchall()
    for extraction in extractions:
        pages = connection.execute(
            """
            SELECT * FROM document_extraction_pages
            WHERE extraction_id = ?
            ORDER BY page_number
            """,
            (extraction["extraction_id"],),
        ).fetchall()
        if (
            len(pages) != extraction["page_count"]
            or [row["page_number"] for row in pages] != list(range(1, len(pages) + 1))
        ):
            raise InstallationBackupError("document_extraction_page_count_failed")
        text_digest = hashlib.sha256()
        total_chars = 0
        for page in pages:
            encoded = str(page["normalized_text"]).encode("utf-8")
            if (
                page["source_id"] != extraction["source_id"]
                or page["person_id"] != extraction["person_id"]
                or page["extracted_chars"] != len(str(page["normalized_text"]))
                or hashlib.sha256(encoded).hexdigest() != page["page_hash"]
            ):
                raise InstallationBackupError("document_extraction_page_integrity_failed")
            text_digest.update(len(encoded).to_bytes(8, "big"))
            text_digest.update(encoded)
            total_chars += int(page["extracted_chars"])
        if (
            total_chars != extraction["total_chars"]
            or text_digest.hexdigest() != extraction["text_hash"]
        ):
            raise InstallationBackupError("document_extraction_integrity_failed")

    candidates = connection.execute(
        """
        SELECT candidate.provenance_locator_json, source.id AS source_id,
               source.person_id, source.content_hash
        FROM candidate_facts AS candidate
        JOIN sources AS source ON source.id = candidate.source_id
        WHERE source.source_type = 'document'
        ORDER BY candidate.id
        """
    ).fetchall()
    for candidate in candidates:
        try:
            locator = json.loads(candidate["provenance_locator_json"])
            if (
                not isinstance(locator, dict)
                or locator.get("kind") != "document_text_span"
                or locator.get("source_id") != candidate["source_id"]
                or locator.get("content_hash") != candidate["content_hash"]
            ):
                raise ValueError
            page = connection.execute(
                """
                SELECT * FROM document_extraction_pages
                WHERE extraction_id = ? AND page_number = ?
                """,
                (locator.get("extraction_id"), locator.get("page_number")),
            ).fetchone()
            start = locator.get("start_codepoint")
            end = locator.get("end_codepoint")
            if (
                page is None
                or page["source_id"] != candidate["source_id"]
                or page["person_id"] != candidate["person_id"]
                or type(start) is not int
                or type(end) is not int
                or start < 0
                or end <= start
                or end > len(str(page["normalized_text"]))
                or hashlib.sha256(
                    str(page["normalized_text"])[start:end].encode("utf-8")
                ).hexdigest()
                != locator.get("selected_text_sha256")
            ):
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise InstallationBackupError(
                "document_provenance_integrity_failed"
            ) from exc


def _validate_family_access(connection: sqlite3.Connection) -> None:
    scoped_tables = (
        "person_access_consent_history",
        "person_access_assignments",
        "access_invitations",
    )
    try:
        for table in scoped_tables:
            rows = connection.execute(
                f"SELECT role, scopes_json FROM {table} ORDER BY rowid"
            ).fetchall()
            for row in rows:
                scopes = json.loads(str(row["scopes_json"]))
                if not valid_role_scopes(str(row["role"]), scopes):
                    raise InstallationBackupError("family_access_consistency_failed")
    except (json.JSONDecodeError, TypeError, sqlite3.Error) as exc:
        raise InstallationBackupError("family_access_consistency_failed") from exc

    inconsistent_queries = (
        """
        SELECT 1 FROM actors AS actor
        WHERE actor.status = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM actor_credentials AS credential
              WHERE credential.actor_id = actor.actor_id AND credential.revoked_at IS NULL
          )
        LIMIT 1
        """,
        """
        SELECT 1 FROM installation_admin_assignments AS assignment
        JOIN actors AS actor ON actor.actor_id = assignment.actor_id
        WHERE assignment.is_active = 1 AND actor.status <> 'active'
        LIMIT 1
        """,
        """
        SELECT 1 FROM actors
        WHERE NOT EXISTS (
            SELECT 1 FROM installation_admin_assignments AS assignment
            JOIN actors AS administrator ON administrator.actor_id = assignment.actor_id
            WHERE assignment.is_active = 1 AND administrator.status = 'active'
        )
        LIMIT 1
        """,
        """
        SELECT 1 FROM person_access_assignments AS assignment
        JOIN actors AS actor ON actor.actor_id = assignment.actor_id
        JOIN people AS person ON person.person_id = assignment.person_id
        WHERE assignment.is_active = 1
          AND (actor.status <> 'active' OR person.is_active <> 1)
        LIMIT 1
        """,
        """
        SELECT 1 FROM own_person_links AS link
        JOIN actors AS actor ON actor.actor_id = link.actor_id
        JOIN people AS person ON person.person_id = link.person_id
        WHERE link.is_active = 1 AND (
            actor.status <> 'active'
            OR person.is_active <> 1
            OR NOT EXISTS (
                SELECT 1 FROM person_access_assignments AS assignment
                WHERE assignment.actor_id = link.actor_id
                  AND assignment.person_id = link.person_id
                  AND assignment.role = 'owner'
                  AND assignment.is_active = 1
            )
        )
        LIMIT 1
        """,
    )
    if any(connection.execute(query).fetchone() is not None for query in inconsistent_queries):
        raise InstallationBackupError("family_access_consistency_failed")


def _validate_security_evidence(connection: sqlite3.Connection) -> None:
    inconsistent_credential = connection.execute(
        """
        SELECT 1
        FROM actor_credentials AS credential
        LEFT JOIN actor_credentials AS replacement
          ON replacement.credential_id = credential.replaced_by_credential_id
        WHERE credential.replaced_by_credential_id IS NOT NULL
          AND (
              replacement.credential_id IS NULL
              OR replacement.actor_id <> credential.actor_id
              OR credential.revoked_at IS NULL
          )
        LIMIT 1
        """
    ).fetchone()
    if inconsistent_credential is not None:
        raise InstallationBackupError("credential_consistency_failed")

    receipt_rows = connection.execute(
        """
        SELECT receipt.*, consent.execution_id AS consent_execution_id,
               consent.actor_id AS consent_actor_id,
               consent.person_id AS consent_person_id,
               consent.envelope_id AS consent_envelope_id
        FROM agent_execution_receipts AS receipt
        LEFT JOIN agent_disclosure_consents AS consent
          ON consent.consent_id = receipt.consent_id
        ORDER BY receipt.receipt_id
        """
    ).fetchall()
    for row in receipt_rows:
        try:
            evidence_ids = json.loads(row["used_evidence_ids_json"])
            used_tools = json.loads(row["used_tools_json"])
            reasons = json.loads(row["reason_codes_json"])
            metadata = json.loads(row["metadata_json"])
            for values in (evidence_ids, used_tools, reasons):
                if (
                    not isinstance(values, list)
                    or not all(isinstance(item, str) for item in values)
                    or values != sorted(set(values))
                ):
                    raise ValueError
            if not isinstance(metadata, dict):
                raise ValueError
            if (
                row["consent_execution_id"] != row["execution_id"]
                or row["consent_actor_id"] != row["actor_id"]
                or row["consent_person_id"] != row["person_id"]
                or row["consent_envelope_id"] != row["envelope_id"]
                or re.fullmatch(r"sha256:[0-9a-f]{64}", row["receipt_id"]) is None
                or re.fullmatch(r"[0-9a-f]{64}", row["receipt_sha256"]) is None
                or (
                    row["output_sha256"] is not None
                    and re.fullmatch(r"[0-9a-f]{64}", row["output_sha256"]) is None
                )
                or (
                    row["status"] == "completed"
                    and (row["output_sha256"] is None or reasons)
                )
                or (
                    row["status"] != "completed"
                    and (row["output_sha256"] is not None or not reasons)
                )
                or parse_utc_datetime(row["completed_at"])
                < parse_utc_datetime(row["started_at"])
            ):
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise InstallationBackupError("execution_receipt_integrity_failed") from exc

    consent_rows = connection.execute(
        """
        SELECT consent_hash, disclosure_metadata_json, metadata_json
        FROM agent_disclosure_consents ORDER BY consent_id
        """
    ).fetchall()
    for row in consent_rows:
        try:
            if (
                re.fullmatch(r"[0-9a-f]{64}", row["consent_hash"]) is None
                or not isinstance(json.loads(row["disclosure_metadata_json"]), dict)
                or not isinstance(json.loads(row["metadata_json"]), dict)
            ):
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise InstallationBackupError("disclosure_consent_integrity_failed") from exc


def _source_payload_relative_path(source_id: str) -> str:
    _validated_source_id(source_id)
    return f"sources/{source_id}/payload.bin"


def _validated_source_id(source_id: str) -> None:
    if SOURCE_ID_PATTERN.fullmatch(source_id) is None:
        raise InstallationBackupError("source_id_unsafe")


def _payload_path(item: object) -> str:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise InstallationBackupError("payload_inventory_invalid")
    path = item["path"]
    assert isinstance(path, str)
    relative = Path(path)
    if (
        relative.is_absolute()
        or relative.anchor
        or ".." in relative.parts
        or path not in {"database.sqlite3"} and not re.fullmatch(
            r"sources/[A-Za-z0-9_-]+/payload\.bin", path
        )
    ):
        raise InstallationBackupError("payload_path_unsafe")
    return path


def _payload_size(item: object) -> int:
    if not isinstance(item, dict) or not isinstance(item.get("size_bytes"), int):
        raise InstallationBackupError("payload_inventory_invalid")
    size = item["size_bytes"]
    assert isinstance(size, int)
    if size < 0:
        raise InstallationBackupError("payload_inventory_invalid")
    return size


def _payload_hash(item: object) -> str:
    if not isinstance(item, dict) or not isinstance(item.get("sha256"), str):
        raise InstallationBackupError("payload_inventory_invalid")
    digest = item["sha256"]
    assert isinstance(digest, str)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise InstallationBackupError("payload_inventory_invalid")
    return digest


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _application_version() -> str | None:
    try:
        return importlib.metadata.version("open-care-proof-kit")
    except importlib.metadata.PackageNotFoundError:
        return None


def _sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_regular_file(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise InstallationBackupError("backup_file_missing")
    return path.read_bytes()


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise InstallationBackupError("symlink_rejected")


def _cleanup_staging(staging: Path | None) -> BaseException | None:
    if staging is None or not _path_exists(staging):
        return None
    try:
        shutil.rmtree(staging)
    except BaseException as exc:
        return exc
    return None
