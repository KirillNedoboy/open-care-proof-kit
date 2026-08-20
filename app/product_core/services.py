from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app.product_core.errors import (
    CandidateNotFoundError,
    CanonicalRecordNotFoundError,
    IntegrityStorageError,
    InvalidTransitionError,
    PersonMismatchError,
    PersonNotFoundError,
    PersonValidationError,
    ProvenanceValidationError,
    SourceCorruptionError,
    SourceNotFoundError,
    SourcePublicationError,
    UnsafeSourcePathError,
)
from app.product_core.models import (
    CandidateDetail,
    CandidateFact,
    CandidateStatus,
    CanonicalRecord,
    ConditionCandidateDetail,
    ConditionCandidateInput,
    FactType,
    LabCandidateDetail,
    LabCandidateInput,
    MedicationCandidateDetail,
    MedicationCandidateInput,
    Person,
    Source,
    SourceType,
    TimelineEvent,
    ensure_utc_datetime,
    normalize_medication_name,
)
from app.product_core.sqlite import SQLiteDatabase, UnitOfWork

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]
MutationAuthorizer = Callable[[sqlite3.Connection], None]
SourceReader = Callable[[Source], bytes]


@dataclass(frozen=True)
class SourceRegistrationResult:
    source: Source
    created: bool


def default_clock() -> datetime:
    return datetime.now(UTC)


def default_id_factory() -> str:
    return str(uuid.uuid4())


class PeopleService:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory

    def create(self, display_name: str, *, date_of_birth: date | None = None) -> Person:
        now = ensure_utc_datetime(self.clock())
        self._validate_date_of_birth(date_of_birth, now)
        person = Person(
            person_id=self.id_factory(),
            display_name=display_name,
            date_of_birth=date_of_birth,
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            uow.people.insert(person)
        return person

    def get(self, person_id: str) -> Person:
        with self.database.uow() as uow:
            person = uow.people.get(person_id)
        if person is None:
            raise PersonNotFoundError(f"person not found: {person_id}")
        return person

    def list_active(self) -> list[Person]:
        with self.database.uow() as uow:
            return uow.people.list_active()

    def update(
        self,
        person_id: str,
        *,
        display_name: str | None = None,
        date_of_birth: date | None = None,
        update_date_of_birth: bool = False,
        authorize: MutationAuthorizer | None = None,
    ) -> Person:
        if display_name is None and not update_date_of_birth:
            raise ValueError("an update field is required")
        now = ensure_utc_datetime(self.clock())
        self._validate_date_of_birth(date_of_birth, now)
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            existing = uow.people.get(person_id)
            if existing is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            person = Person(
                person_id=existing.person_id,
                display_name=existing.display_name if display_name is None else display_name,
                date_of_birth=(
                    existing.date_of_birth if not update_date_of_birth else date_of_birth
                ),
                created_at=existing.created_at,
                updated_at=now,
                is_active=existing.is_active,
            )
            uow.people.update(person)
        return person

    @staticmethod
    def _validate_date_of_birth(value: date | None, now: datetime) -> None:
        if value is not None and value > now.date():
            raise PersonValidationError("date_of_birth cannot be in the future")


class ImmutableSourceStore:
    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self.source_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, relative_path: str, payload: bytes) -> None:
        destination = self._resolve_relative_path(relative_path)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        created_destination = False
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
                created_destination = True
            except FileExistsError as exc:
                raise SourcePublicationError(
                    f"source destination already exists: {relative_path}"
                ) from exc
            finally:
                temporary.unlink(missing_ok=True)

            self._verify(destination, payload)
        except BaseException:
            temporary.unlink(missing_ok=True)
            if created_destination:
                destination.unlink(missing_ok=True)
            raise

    def read(self, source: Source) -> bytes:
        original = self._raw_relative_path(source.relative_path)
        payload = self._read_verified_source_file(original, source, allow_missing=True)
        if payload is not None:
            return payload
        if re.fullmatch(r"[A-Za-z0-9_-]+", source.id) is None:
            raise SourceCorruptionError(f"source ID is unsafe: {source.id}")
        recovered = self.source_dir / source.id / "payload.bin"
        payload = self._read_verified_source_file(recovered, source, allow_missing=False)
        assert payload is not None
        return payload

    def _read_verified_source_file(
        self, path: Path, source: Source, *, allow_missing: bool
    ) -> bytes | None:
        self._reject_unsafe_path_components(path, source.id)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            if allow_missing:
                return None
            raise SourceCorruptionError(
                f"source payload is missing or unreadable: {source.id}"
            ) from None
        except OSError as exc:
            raise SourceCorruptionError(
                f"source payload is missing or unreadable: {source.id}"
            ) from exc
        if not stat.S_ISREG(mode):
            raise SourceCorruptionError(f"source payload is not a regular file: {source.id}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise SourceCorruptionError(
                f"source payload is missing or unreadable: {source.id}"
            ) from exc
        if len(payload) != source.size_bytes:
            raise SourceCorruptionError(f"source size mismatch: {source.id}")
        if hashlib.sha256(payload).hexdigest() != source.content_hash:
            raise SourceCorruptionError(f"source hash mismatch: {source.id}")
        return payload

    def _raw_relative_path(self, relative_path: str) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or relative.anchor or ".." in relative.parts:
            raise UnsafeSourcePathError("source path escapes OPENCARE_SOURCE_DIR")
        return self.source_dir / relative

    @staticmethod
    def _reject_unsafe_path_components(path: Path, source_id: str) -> None:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            try:
                metadata = current.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise SourceCorruptionError(
                    f"source payload is missing or unreadable: {source_id}"
                ) from exc
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if stat.S_ISLNK(metadata.st_mode) or (reparse and attributes & reparse):
                raise SourceCorruptionError(f"source path must not contain links: {source_id}")

    def read_for_portable_export(self, source: Source) -> bytes:
        """Read a source only when its stored location remains a regular local file."""
        path = self._resolve_relative_path(source.relative_path)
        relative = Path(source.relative_path)
        raw_path = self.source_dir.resolve()
        try:
            for part in relative.parts:
                raw_path = raw_path / part
                if stat.S_ISLNK(raw_path.lstat().st_mode):
                    raise SourceCorruptionError(
                        f"source path must not contain symlinks: {source.id}"
                    )
            if not stat.S_ISREG(raw_path.lstat().st_mode):
                raise SourceCorruptionError(
                    f"source payload is not a regular file: {source.id}"
                )
            payload = raw_path.read_bytes()
        except SourceCorruptionError:
            raise
        except OSError as exc:
            raise SourceCorruptionError(
                f"source payload is missing or unreadable: {source.id}"
            ) from exc
        if raw_path.resolve() != path:
            raise SourceCorruptionError(f"source path changed while reading: {source.id}")
        if len(payload) != source.size_bytes:
            raise SourceCorruptionError(f"source size mismatch: {source.id}")
        if hashlib.sha256(payload).hexdigest() != source.content_hash:
            raise SourceCorruptionError(f"source hash mismatch: {source.id}")
        return payload

    def _resolve_relative_path(self, relative_path: str) -> Path:
        relative = Path(relative_path)
        root = self.source_dir.resolve()
        if relative.is_absolute() or relative.anchor:
            raise UnsafeSourcePathError("source path must be relative")
        candidate = (root / relative).resolve()
        if candidate == root or not candidate.is_relative_to(root):
            raise UnsafeSourcePathError("source path escapes OPENCARE_SOURCE_DIR")
        return candidate

    @staticmethod
    def _verify(path: Path, payload: bytes) -> None:
        try:
            if path.stat().st_size != len(payload):
                raise SourcePublicationError("published source size verification failed")
            if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(payload).digest():
                raise SourcePublicationError("published source hash verification failed")
        except OSError as exc:
            raise SourcePublicationError("published source verification failed") from exc


class SourceService:
    def __init__(
        self,
        database: SQLiteDatabase,
        source_dir: Path | str,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
    ) -> None:
        self.database = database
        self.store = ImmutableSourceStore(Path(source_dir))
        self.clock = clock
        self.id_factory = id_factory

    def register_manual_entry(
        self,
        person_id: str,
        name: str,
        *,
        schedule_text: str | None = None,
        note: str | None = None,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> Source:
        return self.register_manual_entry_result(
            person_id,
            name,
            schedule_text=schedule_text,
            note=note,
            provenance=provenance,
            authorize=authorize,
        ).source

    def register_manual_entry_result(
        self,
        person_id: str,
        name: str,
        *,
        schedule_text: str | None = None,
        note: str | None = None,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> SourceRegistrationResult:
        display_name = name.strip()
        if not person_id.strip() or not display_name:
            raise ValueError("person_id and name must not be empty")
        payload = json.dumps(
            {
                "schema_version": 1,
                "source_type": "manual_entry",
                "medication": {
                    "name": display_name,
                    "schedule_text": schedule_text,
                    "note": note,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self._register(
            person_id=person_id,
            source_type="manual_entry",
            payload=payload,
            media_type="application/json",
            suffix="json",
            provenance=provenance or {"entry_method": "manual"},
            authorize=authorize,
        )

    def register_plain_text(
        self,
        person_id: str,
        content: str,
        *,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> Source:
        return self.register_plain_text_result(
            person_id,
            content,
            provenance=provenance,
            authorize=authorize,
        ).source

    def register_plain_text_result(
        self,
        person_id: str,
        content: str,
        *,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> SourceRegistrationResult:
        if not person_id.strip():
            raise ValueError("person_id must not be empty")
        payload = content.encode("utf-8")
        return self._register(
            person_id=person_id,
            source_type="plain_text",
            payload=payload,
            media_type="text/plain",
            suffix="txt",
            provenance=provenance or {"entry_method": "plain_text"},
            authorize=authorize,
        )

    def register_structured_manual_entry_result(
        self,
        person_id: str,
        fact_type: str,
        data: dict[str, object],
        *,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> SourceRegistrationResult:
        """Register a schema_version 2 structured manual source.

        The payload carries fact_type plus typed data; old schema_version 1
        sources remain byte-immutable and are never rewritten.
        """
        if not person_id.strip():
            raise ValueError("person_id must not be empty")
        if fact_type not in ("medication", "condition", "lab"):
            raise ValueError(f"unsupported fact type: {fact_type}")
        payload = json.dumps(
            {
                "schema_version": 2,
                "source_type": "manual_entry",
                "fact_type": fact_type,
                "data": {fact_type: data},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self._register(
            person_id=person_id,
            source_type="manual_entry",
            payload=payload,
            media_type="application/json",
            suffix="json",
            provenance=provenance or {"entry_method": "manual"},
            authorize=authorize,
        )

    def register_structured_manual_entry(
        self,
        person_id: str,
        fact_type: str,
        data: dict[str, object],
        *,
        provenance: dict[str, str] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> Source:
        return self.register_structured_manual_entry_result(
            person_id,
            fact_type,
            data,
            provenance=provenance,
            authorize=authorize,
        ).source

    def get(self, source_id: str) -> Source:
        with self.database.uow() as uow:
            source = uow.sources.get(source_id)
        if source is None:
            raise SourceNotFoundError(f"source not found: {source_id}")
        return source

    def read(self, source_id: str) -> bytes:
        source = self.get(source_id)
        return self.store.read(source)

    def _register(
        self,
        *,
        person_id: str,
        source_type: SourceType,
        payload: bytes,
        media_type: str,
        suffix: str,
        provenance: dict[str, str],
        authorize: MutationAuthorizer | None,
    ) -> SourceRegistrationResult:
        content_hash = hashlib.sha256(payload).hexdigest()
        relative_path: str | None = None
        try:
            with self.database.uow(begin_mode="IMMEDIATE") as uow:
                assert uow.connection is not None
                if authorize is not None:
                    authorize(uow.connection)
                if uow.people.get(person_id) is None:
                    raise PersonNotFoundError(f"person not found: {person_id}")
                existing = uow.sources.find_by_deduplication(
                    person_id, source_type, content_hash
                )
                if existing is not None:
                    self.store.read(existing)
                    return SourceRegistrationResult(existing, False)

                source_id = self._safe_generated_id(self.id_factory())
                relative_path = f"{source_id}.{suffix}"
                self.store.publish(relative_path, payload)
                source = Source(
                    id=source_id,
                    person_id=person_id,
                    source_type=source_type,
                    relative_path=relative_path,
                    content_hash=content_hash,
                    size_bytes=len(payload),
                    media_type=media_type,
                    created_at=ensure_utc_datetime(self.clock()),
                    provenance=provenance,
                )
                uow.sources.insert(source)
                return SourceRegistrationResult(source, True)
        except sqlite3.IntegrityError:
            if relative_path is not None:
                self._remove_unreferenced(relative_path)
            with self.database.uow() as uow:
                existing = uow.sources.find_by_deduplication(
                    person_id, source_type, content_hash
                )
            if existing is not None:
                self.store.read(existing)
                return SourceRegistrationResult(existing, False)
            raise
        except BaseException:
            if relative_path is not None:
                self._remove_unreferenced(relative_path)
            raise

    def _remove_unreferenced(self, relative_path: str) -> None:
        if not self._path_is_referenced(relative_path):
            self.store._resolve_relative_path(relative_path).unlink(missing_ok=True)

    def _path_is_referenced(self, relative_path: str) -> bool:
        with self.database.uow() as uow:
            return uow.sources.path_referenced(relative_path)

    @staticmethod
    def _safe_generated_id(source_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", source_id):
            raise SourcePublicationError("generated source id is not filename-safe")
        return source_id




class FactLifecycleService:
    """The single generic evidence lifecycle for medication, condition, and lab facts.

    Source -> candidate -> human review (pending/confirmed/rejected/unsupported/
    corrected) -> canonical record -> timeline/downstream. Fact-type-specific
    behavior is confined to typed detail models, deterministic event titles, and
    provenance locator semantics; every lifecycle invariant is shared.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
        source_reader: SourceReader | None = None,
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory
        self.source_reader = source_reader

    # ------------------------------------------------------------------ #
    # Candidate creation
    # ------------------------------------------------------------------ #
    def create_candidate(
        self,
        *,
        person_id: str,
        source_id: str,
        fact_type: FactType,
        detail_input: object,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        detail = self._validated_detail(fact_type, detail_input)
        created_at = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            source = uow.sources.get(source_id)
            if source is None:
                raise SourceNotFoundError(f"source not found: {source_id}")
            if source.person_id != person_id:
                raise PersonMismatchError("source belongs to another person")
            locator = self._resolve_provenance_locator(
                source, fact_type, detail, provenance_locator
            )
            candidate = CandidateFact(
                id=self.id_factory(),
                person_id=person_id,
                source_id=source_id,
                fact_type=fact_type,
                detail=detail,
                created_at=created_at,
                provenance_locator=locator,
            )
            uow.candidates.insert(candidate)
        return candidate

    def get_candidate(self, candidate_id: str) -> CandidateFact:
        with self.database.uow() as uow:
            candidate = uow.candidates.get(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
        return candidate

    def list_candidates(
        self,
        person_id: str,
        status: CandidateStatus | None = None,
        *,
        fact_type: str | None = None,
    ) -> list[CandidateFact]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.candidates.list_for_person(person_id, status, fact_type)

    # ------------------------------------------------------------------ #
    # Review decisions
    # ------------------------------------------------------------------ #
    def confirm(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CanonicalRecord:
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            candidate = uow.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
            if candidate.status == "confirmed":
                existing = uow.canonical_records.get_by_candidate(candidate_id)
                if existing is None:
                    raise IntegrityStorageError(
                        f"confirmed candidate has no canonical record: {candidate_id}"
                    )
                return existing
            if candidate.status != "pending":
                raise InvalidTransitionError(
                    f"candidate {candidate_id} cannot be confirmed from {candidate.status}"
                )
            if uow.canonical_records.get_by_candidate(candidate_id) is not None:
                raise IntegrityStorageError(
                    f"pending candidate already has a canonical record: {candidate_id}"
                )
            self._verify_source_and_locator(uow, candidate)

            confirmed_at = ensure_utc_datetime(self.clock())
            superseded = self._find_superseded(uow, candidate)
            canonical = CanonicalRecord(
                id=self.id_factory(),
                person_id=candidate.person_id,
                candidate_id=candidate.id,
                source_id=candidate.source_id,
                fact_type=candidate.fact_type,
                detail=candidate.detail,
                confirmed_at=confirmed_at,
                is_active=True,
                provenance_locator=candidate.provenance_locator,
                predecessor_candidate_id=candidate.predecessor_candidate_id,
            )
            uow.canonical_records.insert(canonical)
            event = TimelineEvent(
                id=self.id_factory(),
                person_id=candidate.person_id,
                canonical_record_id=canonical.id,
                source_id=candidate.source_id,
                fact_type=candidate.fact_type,
                event_type=f"{candidate.fact_type}_confirmed",
                event_at=confirmed_at,
                title=f"{_fact_label(candidate.fact_type)} confirmed: "
                f"{_fact_name(candidate.detail)}",
            )
            uow.timeline_events.insert(event)
            if superseded is not None:
                uow.canonical_records.supersede(superseded.id, canonical.id)
                correction_event = TimelineEvent(
                    id=self.id_factory(),
                    person_id=candidate.person_id,
                    canonical_record_id=superseded.id,
                    source_id=superseded.source_id,
                    fact_type=candidate.fact_type,
                    event_type=f"{candidate.fact_type}_corrected",
                    event_at=confirmed_at,
                    title=f"{_fact_label(candidate.fact_type)} corrected: "
                    f"{_fact_name(superseded.detail)}",
                )
                uow.timeline_events.insert(correction_event)
            uow.candidates.update_status(candidate.id, "confirmed", confirmed_at)
            return canonical

    def reject(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return self._terminal_review(candidate_id, "rejected", authorize)

    def unsupported(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return self._terminal_review(candidate_id, "unsupported", authorize)

    def _terminal_review(
        self,
        candidate_id: str,
        status: CandidateStatus,
        authorize: MutationAuthorizer | None,
    ) -> CandidateFact:
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            candidate = uow.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
            if candidate.status != "pending":
                raise InvalidTransitionError(
                    f"candidate {candidate_id} cannot be marked {status} from "
                    f"{candidate.status}"
                )
            reviewed_at = ensure_utc_datetime(self.clock())
            uow.candidates.update_status(candidate.id, status, reviewed_at)
            candidate.status = status
            candidate.reviewed_at = reviewed_at
            return candidate

    def correct(
        self,
        candidate_id: str,
        *,
        detail_input: object,
        source_id: str | None = None,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if authorize is not None:
                authorize(uow.connection)
            original = uow.candidates.get(candidate_id)
            if original is None:
                raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
            if original.status == "confirmed":
                existing = uow.canonical_records.get_by_candidate(candidate_id)
                if existing is None:
                    raise IntegrityStorageError(
                        f"confirmed candidate has no canonical record: {candidate_id}"
                    )
                if not existing.is_active:
                    raise InvalidTransitionError(
                        f"candidate {candidate_id} cannot be corrected from a "
                        "superseded record"
                    )
            elif original.status != "pending":
                raise InvalidTransitionError(
                    f"candidate {candidate_id} cannot be corrected from {original.status}"
                )
            detail = self._validated_detail(original.fact_type, detail_input)
            replacement_source_id = source_id or original.source_id
            source = uow.sources.get(replacement_source_id)
            if source is None:
                raise SourceNotFoundError(f"source not found: {replacement_source_id}")
            if source.person_id != original.person_id:
                raise PersonMismatchError("replacement source belongs to another person")
            locator = self._resolve_provenance_locator(
                source, original.fact_type, detail, provenance_locator
            )
            reviewed_at = ensure_utc_datetime(self.clock())
            replacement = CandidateFact(
                id=self.id_factory(),
                person_id=original.person_id,
                source_id=replacement_source_id,
                fact_type=original.fact_type,
                detail=detail,
                created_at=reviewed_at,
                predecessor_candidate_id=original.id,
                provenance_locator=locator,
            )
            if original.status == "pending":
                uow.candidates.update_status(original.id, "corrected", reviewed_at)
            uow.candidates.insert(replacement)
            return replacement

    # ------------------------------------------------------------------ #
    # Canonical records and timeline
    # ------------------------------------------------------------------ #
    def list_active(
        self,
        person_id: str,
        *,
        fact_type: str | None = None,
    ) -> list[CanonicalRecord]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.canonical_records.list_active_for_person(person_id, fact_type)

    def get_canonical(self, record_id: str) -> CanonicalRecord:
        with self.database.uow() as uow:
            record = uow.canonical_records.get(record_id)
        if record is None:
            raise CanonicalRecordNotFoundError(f"canonical record not found: {record_id}")
        return record

    def list_canonical(
        self,
        person_id: str,
        *,
        include_inactive: bool = False,
        fact_type: str | None = None,
    ) -> list[CanonicalRecord]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.canonical_records.list_for_person(
                person_id, include_inactive, fact_type
            )

    def list_timeline(self, person_id: str) -> list[TimelineEvent]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.timeline_events.list_for_person(person_id)

    # ------------------------------------------------------------------ #
    # Typed detail construction and provenance locator resolution
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validated_detail(fact_type: str, detail_input: object) -> CandidateDetail:
        if fact_type == "medication":
            if not isinstance(detail_input, MedicationCandidateInput):
                raise ValueError("medication detail input is required")
            return MedicationCandidateDetail(
                display_name=detail_input.display_name,
                normalized_name=normalize_medication_name(detail_input.display_name),
                schedule_text=detail_input.schedule_text,
                note=detail_input.note,
            )
        if fact_type == "condition":
            if not isinstance(detail_input, ConditionCandidateInput):
                raise ValueError("condition detail input is required")
            return ConditionCandidateDetail(
                display_name=detail_input.display_name,
                normalized_name=normalize_medication_name(detail_input.display_name),
                status_text=detail_input.status_text,
                onset_date=detail_input.onset_date,
                note=detail_input.note,
            )
        if fact_type == "lab":
            if not isinstance(detail_input, LabCandidateInput):
                raise ValueError("lab detail input is required")
            return LabCandidateDetail(
                test_name=detail_input.test_name,
                normalized_test_name=normalize_medication_name(detail_input.test_name),
                result_text=detail_input.result_text,
                unit_text=detail_input.unit_text,
                reference_range_text=detail_input.reference_range_text,
                observed_date=detail_input.observed_date,
                source_flag_text=detail_input.source_flag_text,
                note=detail_input.note,
            )
        raise ValueError(f"unsupported fact type: {fact_type}")

    def _resolve_provenance_locator(
        self,
        source: Source,
        fact_type: str,
        detail: CandidateDetail,
        client_locator: dict[str, object] | None,
    ) -> dict[str, object]:
        if source.source_type == "manual_entry":
            locator: dict[str, object] = {
                "kind": "structured_field",
                "path": self._manual_locator_path(source, fact_type),
            }
        else:
            if client_locator is None:
                raise ProvenanceValidationError(
                    "provenance locator is required for plain-text sources"
                )
            locator = client_locator
            if (
                locator.get("kind") != "span"
                or not isinstance(locator.get("start"), int)
                or not isinstance(locator.get("end"), int)
            ):
                raise ProvenanceValidationError(
                    "provenance locator must be a span with integer start/end offsets"
                )
        if self.source_reader is not None:
            payload = self.source_reader(source)
            self._validate_locator_content(source, fact_type, detail, locator, payload)
        return locator

    def _manual_locator_path(self, source: Source, fact_type: str) -> str:
        if self.source_reader is None:
            # No reader: assume the legacy schema_version 1 payload shape whose
            # medication object is the only structure this code path ever wrote.
            return "medication"
        payload = self.source_reader(source)
        try:
            parsed = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise ProvenanceValidationError("manual source payload is not valid JSON") from None
        if isinstance(parsed, dict) and parsed.get("schema_version") == 2:
            name_field = "test_name" if fact_type == "lab" else "display_name"
            return f"data.{fact_type}.{name_field}"
        return "medication"

    @staticmethod
    def _validate_locator_content(
        source: Source,
        fact_type: str,
        detail: CandidateDetail,
        locator: dict[str, object],
        payload: bytes,
    ) -> None:
        expected = _fact_name(detail)
        if source.source_type == "manual_entry":
            try:
                parsed = json.loads(payload)
            except (ValueError, UnicodeDecodeError):
                raise ProvenanceValidationError("manual source payload is not valid JSON") from None
            path = locator.get("path")
            if not isinstance(path, str):
                raise ProvenanceValidationError("structured provenance locator requires a path")
            value: object = parsed
            for part in path.split("."):
                if not isinstance(value, dict) or part not in value:
                    raise ProvenanceValidationError(
                        f"provenance locator path does not exist in source: {path}"
                    )
                value = value[part]
            if isinstance(value, str):
                matches = value.strip() == expected
            elif isinstance(value, dict) and isinstance(value.get("name"), str):
                matches = str(value["name"]).strip() == expected
            else:
                matches = False
            schema_version = parsed.get("schema_version") if isinstance(parsed, dict) else None
            if schema_version == 2:
                if not matches:
                    raise ProvenanceValidationError(
                        f"provenance locator value does not match {fact_type} name"
                    )
            elif not (
                isinstance(value, str)
                or (isinstance(value, dict) and isinstance(value.get("name"), str))
            ):
                # Legacy schema_version 1 manual sources carry a single
                # medication structure; the locator must point at the recorded
                # name field. The candidate display name may be a reviewer
                # normalization differing from the registered source name,
                # because the two-step source-then-candidate flow predates P1
                # and is preserved byte-compatibly.
                raise ProvenanceValidationError(
                    "provenance locator does not point at a recorded name field"
                )
            return
        start = locator.get("start")
        end = locator.get("end")
        assert isinstance(start, int) and isinstance(end, int)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise ProvenanceValidationError("plain-text source is not valid UTF-8") from None
        if start < 0 or end <= start or end > len(text):
            raise ProvenanceValidationError("provenance span is out of range")
        if text[start:end].strip() != expected:
            raise ProvenanceValidationError("provenance span does not match the recorded name")

    def _verify_source_and_locator(
        self, uow: UnitOfWork, candidate: CandidateFact
    ) -> None:
        if self.source_reader is None:
            return
        source = uow.sources.get(candidate.source_id)
        if source is None:
            raise IntegrityStorageError(f"candidate source is missing: {candidate.source_id}")
        payload = self.source_reader(source)
        if candidate.provenance_locator is not None:
            self._validate_locator_content(
                source,
                candidate.fact_type,
                candidate.detail,
                candidate.provenance_locator,
                payload,
            )

    @staticmethod
    def _find_superseded(
        uow: UnitOfWork, candidate: CandidateFact
    ) -> CanonicalRecord | None:
        if candidate.predecessor_candidate_id is None:
            return None
        predecessor = uow.candidates.get(candidate.predecessor_candidate_id)
        if predecessor is None or predecessor.status != "confirmed":
            return None
        existing = uow.canonical_records.get_by_candidate(predecessor.id)
        if existing is None or not existing.is_active:
            return None
        return existing


class MedicationLifecycleService(FactLifecycleService):
    """Medication compatibility facade over the generic evidence lifecycle.

    Public signatures and behavior are unchanged; internally every operation
    delegates to the generic lifecycle with medication-typed detail.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
        source_reader: SourceReader | None = None,
    ) -> None:
        super().__init__(database, clock=clock, id_factory=id_factory, source_reader=source_reader)

    def create_candidate(  # type: ignore[override]  # medication-only facade surface
        self,
        *,
        person_id: str,
        source_id: str,
        display_name: str,
        schedule_text: str | None = None,
        note: str | None = None,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return super().create_candidate(
            person_id=person_id,
            source_id=source_id,
            fact_type="medication",
            detail_input=MedicationCandidateInput(
                display_name=display_name,
                schedule_text=schedule_text,
                note=note,
            ),
            provenance_locator=provenance_locator,
            authorize=authorize,
        )

    def get_candidate(self, candidate_id: str) -> CandidateFact:
        return super().get_candidate(candidate_id)

    def create_fact_candidate(
        self,
        *,
        person_id: str,
        source_id: str,
        fact_type: FactType,
        detail_input: object,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        """Generic fact-family candidate creation (condition/lab)."""
        return super().create_candidate(
            person_id=person_id,
            source_id=source_id,
            fact_type=fact_type,
            detail_input=detail_input,
            provenance_locator=provenance_locator,
            authorize=authorize,
        )

    def correct_fact_candidate(
        self,
        candidate_id: str,
        *,
        detail_input: object,
        source_id: str | None = None,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        """Generic correction for non-medication fact families."""
        return super().correct(
            candidate_id,
            detail_input=detail_input,
            source_id=source_id,
            provenance_locator=provenance_locator,
            authorize=authorize,
        )

    def list_candidates(  # type: ignore[override]  # medication facade keeps the generic listing surface
        self,
        person_id: str,
        status: CandidateStatus | None = None,
    ) -> list[CandidateFact]:
        return super().list_candidates(person_id, status)

    def list_fact_candidates(
        self,
        person_id: str,
        status: CandidateStatus | None = None,
        *,
        fact_type: str,
    ) -> list[CandidateFact]:
        """Generic fact-family candidate listing (condition/lab)."""
        return super().list_candidates(person_id, status, fact_type=fact_type)

    def confirm(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CanonicalRecord:
        return super().confirm(candidate_id, authorize=authorize)

    def correct(  # type: ignore[override]  # medication-only facade surface
        self,
        candidate_id: str,
        *,
        display_name: str,
        schedule_text: str | None = None,
        note: str | None = None,
        source_id: str | None = None,
        provenance_locator: dict[str, object] | None = None,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return super().correct(
            candidate_id,
            detail_input=MedicationCandidateInput(
                display_name=display_name,
                schedule_text=schedule_text,
                note=note,
            ),
            source_id=source_id,
            provenance_locator=provenance_locator,
            authorize=authorize,
        )

    def reject(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return super().reject(candidate_id, authorize=authorize)

    def unsupported(
        self,
        candidate_id: str,
        *,
        authorize: MutationAuthorizer | None = None,
    ) -> CandidateFact:
        return super().unsupported(candidate_id, authorize=authorize)

    def list_active(  # type: ignore[override]  # medication-only facade surface
        self, person_id: str
    ) -> list[CanonicalRecord]:
        return super().list_active(person_id, fact_type="medication")

    def list_fact_canonical(
        self,
        person_id: str,
        *,
        include_inactive: bool = False,
        fact_type: str,
    ) -> list[CanonicalRecord]:
        """Generic fact-family canonical listing (condition/lab)."""
        return super().list_canonical(
            person_id, include_inactive=include_inactive, fact_type=fact_type
        )

    def list_canonical(  # type: ignore[override]  # medication-only facade surface
        self,
        person_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[CanonicalRecord]:
        return super().list_canonical(
            person_id, include_inactive=include_inactive, fact_type="medication"
        )

    def list_timeline(self, person_id: str) -> list[TimelineEvent]:
        return super().list_timeline(person_id)


def _fact_label(fact_type: str) -> str:
    return {"medication": "Medication", "condition": "Condition", "lab": "Lab"}[fact_type]


def _fact_name(detail: CandidateDetail) -> str:
    if isinstance(detail, MedicationCandidateDetail):
        return detail.display_name
    if isinstance(detail, ConditionCandidateDetail):
        return detail.display_name
    if isinstance(detail, LabCandidateDetail):
        return detail.test_name
    raise ValueError("unsupported candidate detail")
