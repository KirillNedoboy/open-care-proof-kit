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
    IntegrityStorageError,
    InvalidTransitionError,
    PersonMismatchError,
    PersonNotFoundError,
    PersonValidationError,
    SourceCorruptionError,
    SourceNotFoundError,
    SourcePublicationError,
    UnsafeSourcePathError,
)
from app.product_core.models import (
    CandidateFact,
    CandidateStatus,
    CanonicalMedicationRecord,
    MedicationCandidateInput,
    Person,
    Source,
    SourceType,
    TimelineEvent,
    ensure_utc_datetime,
    normalize_medication_name,
)
from app.product_core.sqlite import SQLiteDatabase

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


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
    ) -> Person:
        if display_name is None and not update_date_of_birth:
            raise ValueError("an update field is required")
        now = ensure_utc_datetime(self.clock())
        self._validate_date_of_birth(date_of_birth, now)
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
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
        path = self._resolve_relative_path(source.relative_path)
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
    ) -> Source:
        return self.register_manual_entry_result(
            person_id,
            name,
            schedule_text=schedule_text,
            note=note,
            provenance=provenance,
        ).source

    def register_manual_entry_result(
        self,
        person_id: str,
        name: str,
        *,
        schedule_text: str | None = None,
        note: str | None = None,
        provenance: dict[str, str] | None = None,
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
        )

    def register_plain_text(
        self,
        person_id: str,
        content: str,
        *,
        provenance: dict[str, str] | None = None,
    ) -> Source:
        return self.register_plain_text_result(
            person_id,
            content,
            provenance=provenance,
        ).source

    def register_plain_text_result(
        self,
        person_id: str,
        content: str,
        *,
        provenance: dict[str, str] | None = None,
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
        )

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
    ) -> SourceRegistrationResult:
        content_hash = hashlib.sha256(payload).hexdigest()
        relative_path: str | None = None
        try:
            with self.database.uow(begin_mode="IMMEDIATE") as uow:
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


class MedicationLifecycleService:
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

    def create_candidate(
        self,
        *,
        person_id: str,
        source_id: str,
        display_name: str,
        schedule_text: str | None,
        note: str | None,
    ) -> CandidateFact:
        input_data = MedicationCandidateInput(
            display_name=display_name,
            schedule_text=schedule_text,
            note=note,
        )
        created_at = ensure_utc_datetime(self.clock())
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            source = uow.sources.get(source_id)
            if source is None:
                raise SourceNotFoundError(f"source not found: {source_id}")
            if source.person_id != person_id:
                raise PersonMismatchError("source belongs to another person")
            candidate = CandidateFact(
                id=self.id_factory(),
                person_id=person_id,
                source_id=source_id,
                display_name=input_data.display_name,
                normalized_name=normalize_medication_name(input_data.display_name),
                schedule_text=input_data.schedule_text,
                note=input_data.note,
                created_at=created_at,
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
    ) -> list[CandidateFact]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.candidates.list_for_person(person_id, status)

    def confirm(self, candidate_id: str) -> CanonicalMedicationRecord:
        with self.database.uow() as uow:
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

            confirmed_at = ensure_utc_datetime(self.clock())
            canonical = CanonicalMedicationRecord(
                id=self.id_factory(),
                person_id=candidate.person_id,
                candidate_id=candidate.id,
                source_id=candidate.source_id,
                display_name=candidate.display_name,
                normalized_name=candidate.normalized_name,
                schedule_text=candidate.schedule_text,
                note=candidate.note,
                confirmed_at=confirmed_at,
                is_active=True,
            )
            event = TimelineEvent(
                id=self.id_factory(),
                person_id=candidate.person_id,
                canonical_record_id=canonical.id,
                source_id=candidate.source_id,
                event_type="medication_confirmed",
                event_at=confirmed_at,
                title=f"Medication confirmed: {candidate.display_name}",
            )
            uow.canonical_records.insert(canonical)
            uow.timeline_events.insert(event)
            uow.candidates.update_status(candidate.id, "confirmed", confirmed_at)
            return canonical

    def correct(
        self,
        candidate_id: str,
        *,
        display_name: str,
        schedule_text: str | None = None,
        note: str | None = None,
        source_id: str | None = None,
    ) -> CandidateFact:
        input_data = MedicationCandidateInput(
            display_name=display_name,
            schedule_text=schedule_text,
            note=note,
        )
        with self.database.uow() as uow:
            original = uow.candidates.get(candidate_id)
            if original is None:
                raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
            if original.status != "pending":
                raise InvalidTransitionError(
                    f"candidate {candidate_id} cannot be corrected from {original.status}"
                )
            replacement_source_id = source_id or original.source_id
            source = uow.sources.get(replacement_source_id)
            if source is None:
                raise SourceNotFoundError(f"source not found: {replacement_source_id}")
            if source.person_id != original.person_id:
                raise PersonMismatchError("replacement source belongs to another person")
            reviewed_at = ensure_utc_datetime(self.clock())
            replacement = CandidateFact(
                id=self.id_factory(),
                person_id=original.person_id,
                source_id=replacement_source_id,
                display_name=input_data.display_name,
                normalized_name=normalize_medication_name(input_data.display_name),
                schedule_text=input_data.schedule_text,
                note=input_data.note,
                created_at=reviewed_at,
                predecessor_candidate_id=original.id,
            )
            uow.candidates.update_status(original.id, "corrected", reviewed_at)
            uow.candidates.insert(replacement)
            return replacement

    def reject(self, candidate_id: str) -> CandidateFact:
        with self.database.uow() as uow:
            candidate = uow.candidates.get(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate not found: {candidate_id}")
            if candidate.status != "pending":
                raise InvalidTransitionError(
                    f"candidate {candidate_id} cannot be rejected from {candidate.status}"
                )
            reviewed_at = ensure_utc_datetime(self.clock())
            uow.candidates.update_status(candidate.id, "rejected", reviewed_at)
            candidate.status = "rejected"
            candidate.reviewed_at = reviewed_at
            return candidate

    def list_active(self, person_id: str) -> list[CanonicalMedicationRecord]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.canonical_records.list_active_for_person(person_id)

    def list_canonical(
        self,
        person_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[CanonicalMedicationRecord]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.canonical_records.list_for_person(person_id, include_inactive)

    def list_timeline(self, person_id: str) -> list[TimelineEvent]:
        with self.database.uow() as uow:
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            return uow.timeline_events.list_for_person(person_id)
