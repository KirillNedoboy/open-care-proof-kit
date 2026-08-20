from __future__ import annotations

import hashlib
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.product_core.errors import IntegrityStorageError, PersonNotFoundError
from app.product_core.migrations import PRODUCT_MIGRATIONS
from app.product_core.models import (
    CandidateFact,
    CanonicalRecord,
    ConditionCandidateDetail,
    DocumentExtractionPage,
    DocumentExtractionSnapshot,
    LabCandidateDetail,
    MedicationCandidateDetail,
    PersistedVisitBrief,
    PersistedVisitBriefRevision,
    Person,
    Source,
    TimelineEvent,
    Visit,
    VisitBriefEvidenceSelection,
    VisitQuestion,
    isoformat_utc,
)
from app.product_core.persisted_visit_briefs import verify_persisted_visit_brief_revision
from app.product_core.services import ImmutableSourceStore
from app.product_core.sqlite import SQLiteDatabase

PORTABLE_VAULT_FORMAT_VERSION = 4
PRODUCT_CORE_SCHEMA_VERSION = PRODUCT_MIGRATIONS[-1].version


@dataclass(frozen=True)
class PortableVaultExport:
    zip_bytes: bytes
    vault_json: bytes
    manifest_json: bytes


class PortableVaultExportService:
    """Create a deterministic logical, Person-scoped portable vault archive."""

    def __init__(
        self,
        database: SQLiteDatabase,
        source_store: ImmutableSourceStore | Path | str,
    ) -> None:
        self.database = database
        self.source_store = (
            source_store
            if isinstance(source_store, ImmutableSourceStore)
            else ImmutableSourceStore(Path(source_store))
        )

    def export(self, person_id: str) -> PortableVaultExport:
        with self.database.uow() as uow:
            person = uow.people.get(person_id)
            if person is None:
                raise PersonNotFoundError(f"person not found: {person_id}")
            candidates = sorted(
                uow.candidates.list_for_person(person_id),
                key=lambda item: (isoformat_utc(item.created_at), item.id),
            )
            records = sorted(
                uow.canonical_records.list_for_person(person_id, include_inactive=True),
                key=lambda item: (isoformat_utc(item.confirmed_at), item.id),
            )
            events = sorted(
                uow.timeline_events.list_for_person(person_id),
                key=lambda item: (isoformat_utc(item.event_at), item.id),
            )
            visits = sorted(
                uow.visits.list_for_person(person_id),
                key=lambda item: (isoformat_utc(item.created_at), item.visit_id),
            )

            questions_by_visit: dict[str, list[VisitQuestion]] = {}
            briefs: list[tuple[PersistedVisitBrief, list[PersistedVisitBriefRevision]]]
            briefs = []
            selections_by_revision: dict[str, list[VisitBriefEvidenceSelection]] = {}
            for visit in visits:
                questions_by_visit[visit.visit_id] = sorted(
                    uow.visit_questions.list_for_visit(visit.visit_id),
                    key=lambda item: (item.position, item.question_id),
                )
                brief = uow.visit_briefs.get_by_visit(visit.visit_id)
                if brief is None:
                    continue
                revisions = sorted(
                    uow.visit_brief_revisions.list_for_brief(brief.brief_id),
                    key=lambda item: (item.revision_number, item.revision_id),
                )
                for revision in revisions:
                    verify_persisted_visit_brief_revision(revision)
                    selections_by_revision[revision.revision_id] = sorted(
                        uow.visit_brief_evidence.list_for_revision(revision.revision_id),
                        key=lambda item: (item.position, item.canonical_record_id),
                    )
                briefs.append((brief, revisions))

            sources = sorted(
                (
                    item
                    for item in uow.sources.list_for_person(person_id)
                    if item.source_type != "genetics"
                ),
                key=lambda item: (isoformat_utc(item.created_at), item.id),
            )
            source_payloads: dict[str, bytes] = {}
            document_extractions: list[DocumentExtractionSnapshot] = []
            document_pages: list[DocumentExtractionPage] = []
            for source in sources:
                _source_archive_path(source)
                source_payloads[source.id] = self.source_store.read_for_portable_export(source)
                if source.source_type != "document":
                    continue
                extraction = uow.document_extractions.get_complete_for_source(source.id)
                if extraction is None:
                    raise IntegrityStorageError(f"document extraction is missing: {source.id}")
                pages = uow.document_extractions.list_pages(extraction.extraction_id)
                _verify_document_extraction(source, extraction, pages)
                document_extractions.append(extraction)
                document_pages.extend(pages)
            connection = uow.connection
            assert connection is not None
            memberships = [
                _membership_dto(row)
                for row in connection.execute(
                    "SELECT * FROM family_memberships WHERE person_id = ? "
                    "ORDER BY created_at, membership_id",
                    (person_id,),
                ).fetchall()
            ]
            family_ids = sorted({str(item["family_id"]) for item in memberships})
            families = []
            for family_id in family_ids:
                family = connection.execute(
                    "SELECT * FROM families WHERE family_id = ?", (family_id,)
                ).fetchone()
                if family is None:
                    raise IntegrityStorageError("export family is missing")
                families.append(_family_dto(family))
            relationships = [
                _relationship_dto(row)
                for row in connection.execute(
                    """
                    SELECT * FROM person_relationships
                    WHERE person_id = ? OR related_person_id = ?
                    ORDER BY created_at, relationship_id
                    """,
                    (person_id, person_id),
                ).fetchall()
            ]
            consents = [
                _consent_dto(row)
                for row in connection.execute(
                    "SELECT * FROM person_access_consent_history WHERE person_id = ? "
                    "ORDER BY created_at, consent_event_id",
                    (person_id,),
                ).fetchall()
            ]
            assignments = [
                _assignment_dto(row)
                for row in connection.execute(
                    "SELECT * FROM person_access_assignments WHERE person_id = ? "
                    "ORDER BY granted_at, assignment_id",
                    (person_id,),
                ).fetchall()
            ]
            actor_ids = _relevant_actor_ids(
                memberships, relationships, families, consents, assignments
            )
            actors = []
            for actor_id in sorted(actor_ids):
                actor = connection.execute(
                    "SELECT actor_id, display_name, status, created_at FROM actors "
                    "WHERE actor_id = ?",
                    (actor_id,),
                ).fetchone()
                if actor is None:
                    raise IntegrityStorageError("export Actor history is incomplete")
                actors.append(_actor_dto(actor))

        candidates_by_id = {candidate.id: candidate for candidate in candidates}
        vault_json = _canonical_json_bytes(
            {
                "format_version": PORTABLE_VAULT_FORMAT_VERSION,
                "person": _person_dto(person),
                "sources": [_source_dto(source) for source in sources],
                "document_extractions": [
                    _document_extraction_dto(item) for item in document_extractions
                ],
                "document_extraction_pages": [
                    _document_extraction_page_dto(item) for item in document_pages
                ],
                "candidate_facts": [_candidate_dto(item) for item in candidates],
                "candidate_medication_details": [
                    _candidate_medication_detail_dto(item)
                    for item in candidates
                    if item.fact_type == "medication"
                ],
                "candidate_condition_details": [
                    _candidate_condition_detail_dto(item)
                    for item in candidates
                    if item.fact_type == "condition"
                ],
                "candidate_lab_details": [
                    _candidate_lab_detail_dto(item)
                    for item in candidates
                    if item.fact_type == "lab"
                ],
                "canonical_records": [
                    _canonical_record_dto(item, candidates_by_id[item.candidate_id])
                    for item in records
                ],
                "canonical_medication_details": [
                    _canonical_medication_detail_dto(item)
                    for item in records
                    if item.fact_type == "medication"
                ],
                "canonical_condition_details": [
                    _canonical_condition_detail_dto(item)
                    for item in records
                    if item.fact_type == "condition"
                ],
                "canonical_lab_details": [
                    _canonical_lab_detail_dto(item) for item in records if item.fact_type == "lab"
                ],
                "timeline_events": [_timeline_event_dto(item) for item in events],
                "visits": [_visit_dto(item) for item in visits],
                "visit_questions": [
                    _question_dto(question)
                    for visit in visits
                    for question in questions_by_visit[visit.visit_id]
                ],
                "visit_briefs": [_brief_dto(brief, revisions) for brief, revisions in briefs],
                "visit_brief_revisions": [
                    _revision_dto(revision)
                    for _brief, revisions in briefs
                    for revision in revisions
                ],
                "visit_brief_evidence_selections": [
                    _selection_dto(revision.revision_id, selection)
                    for _brief, revisions in briefs
                    for revision in revisions
                    for selection in selections_by_revision[revision.revision_id]
                ],
                "families": families,
                "family_memberships": memberships,
                "person_relationships": relationships,
                "person_access_consent_history": consents,
                "person_access_assignments": assignments,
                "actors": actors,
            }
        )
        entries: list[tuple[str, bytes]] = [("vault.json", vault_json)]
        entries.extend(
            (_source_archive_path(source), source_payloads[source.id]) for source in sources
        )
        manifest_json = _canonical_json_bytes(
            {
                "format_version": PORTABLE_VAULT_FORMAT_VERSION,
                "product_core_schema_version": PRODUCT_CORE_SCHEMA_VERSION,
                "person_id": person.person_id,
                "payloads": [
                    {
                        "path": path,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size_bytes": len(payload),
                    }
                    for path, payload in entries
                ],
            }
        )
        manifest_hash = hashlib.sha256(manifest_json).hexdigest().encode("ascii")
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as artifact:
            with zipfile.ZipFile(
                artifact, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                _write_deterministic(archive, "manifest.json", manifest_json)
                _write_deterministic(archive, "manifest.sha256", manifest_hash)
                _write_deterministic(archive, "vault.json", vault_json)
                for path, payload in entries[1:]:
                    _write_deterministic(archive, path, payload)
            artifact.seek(0)
            return PortableVaultExport(
                zip_bytes=artifact.read(), vault_json=vault_json, manifest_json=manifest_json
            )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _write_deterministic(archive: zipfile.ZipFile, path: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _source_archive_path(source: Source) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source.id):
        raise IntegrityStorageError(f"export source ID is not archive-safe: {source.id}")
    return f"sources/{source.id}/payload.bin"


def _person_dto(person: Person) -> dict[str, object]:
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "date_of_birth": None if person.date_of_birth is None else person.date_of_birth.isoformat(),
        "created_at": isoformat_utc(person.created_at),
        "updated_at": isoformat_utc(person.updated_at),
        "is_active": person.is_active,
    }


def _source_dto(source: Source) -> dict[str, object]:
    original_filename = source.original_filename
    if original_filename is not None and (
        "/" in original_filename
        or "\\" in original_filename
        or "\x00" in original_filename
        or original_filename in {".", ".."}
    ):
        raise IntegrityStorageError(f"export source filename is not metadata-safe: {source.id}")
    return {
        "source_id": source.id,
        "person_id": source.person_id,
        "source_type": source.source_type,
        "content_hash": source.content_hash,
        "size_bytes": source.size_bytes,
        "media_type": source.media_type,
        "original_filename": original_filename,
        "document_kind": source.document_kind,
        "created_at": isoformat_utc(source.created_at),
    }


def _verify_document_extraction(
    source: Source,
    extraction: DocumentExtractionSnapshot,
    pages: list[DocumentExtractionPage],
) -> None:
    if (
        extraction.source_id != source.id
        or extraction.person_id != source.person_id
        or len(pages) != extraction.page_count
        or [page.page_number for page in pages] != list(range(1, len(pages) + 1))
    ):
        raise IntegrityStorageError("document extraction identity mismatch")
    text_digest = hashlib.sha256()
    total_chars = 0
    for page in pages:
        encoded = page.normalized_text.encode("utf-8")
        if (
            page.extraction_id != extraction.extraction_id
            or page.source_id != source.id
            or page.person_id != source.person_id
            or page.extracted_chars != len(page.normalized_text)
            or hashlib.sha256(encoded).hexdigest() != page.page_hash
        ):
            raise IntegrityStorageError("document extraction page integrity mismatch")
        text_digest.update(len(encoded).to_bytes(8, "big"))
        text_digest.update(encoded)
        total_chars += page.extracted_chars
    if total_chars != extraction.total_chars or text_digest.hexdigest() != extraction.text_hash:
        raise IntegrityStorageError("document extraction integrity mismatch")


def _document_extraction_dto(
    extraction: DocumentExtractionSnapshot,
) -> dict[str, object]:
    return {
        "extraction_id": extraction.extraction_id,
        "source_id": extraction.source_id,
        "person_id": extraction.person_id,
        "extractor": extraction.extractor,
        "extractor_version": extraction.extractor_version,
        "status": extraction.status,
        "text_hash": extraction.text_hash,
        "total_chars": extraction.total_chars,
        "page_count": extraction.page_count,
        "extracted_at": isoformat_utc(extraction.extracted_at),
    }


def _document_extraction_page_dto(
    page: DocumentExtractionPage,
) -> dict[str, object]:
    return {
        "extraction_id": page.extraction_id,
        "source_id": page.source_id,
        "person_id": page.person_id,
        "page_number": page.page_number,
        "normalized_text": page.normalized_text,
        "decoded_content_bytes": page.decoded_content_bytes,
        "extracted_chars": page.extracted_chars,
        "page_hash": page.page_hash,
    }


def _candidate_dto(candidate: CandidateFact) -> dict[str, object]:
    return {
        "candidate_id": candidate.id,
        "person_id": candidate.person_id,
        "source_id": candidate.source_id,
        "fact_type": candidate.fact_type,
        "status": candidate.status,
        "created_at": isoformat_utc(candidate.created_at),
        "reviewed_at": (
            None if candidate.reviewed_at is None else isoformat_utc(candidate.reviewed_at)
        ),
        "predecessor_candidate_id": candidate.predecessor_candidate_id,
        "provenance_locator": candidate.provenance_locator,
    }


def _candidate_medication_detail_dto(candidate: CandidateFact) -> dict[str, object]:
    detail = candidate.detail
    assert isinstance(detail, MedicationCandidateDetail)
    return {
        "candidate_id": candidate.id,
        "display_name": detail.display_name,
        "normalized_name": detail.normalized_name,
        "schedule_text": detail.schedule_text,
        "note": detail.note,
    }


def _candidate_condition_detail_dto(candidate: CandidateFact) -> dict[str, object]:
    detail = candidate.detail
    assert isinstance(detail, ConditionCandidateDetail)
    return {
        "candidate_id": candidate.id,
        "display_name": detail.display_name,
        "normalized_name": detail.normalized_name,
        "status_text": detail.status_text,
        "onset_date": (None if detail.onset_date is None else detail.onset_date.isoformat()),
        "note": detail.note,
    }


def _candidate_lab_detail_dto(candidate: CandidateFact) -> dict[str, object]:
    detail = candidate.detail
    assert isinstance(detail, LabCandidateDetail)
    return {
        "candidate_id": candidate.id,
        "test_name": detail.test_name,
        "normalized_test_name": detail.normalized_test_name,
        "result_text": detail.result_text,
        "unit_text": detail.unit_text,
        "reference_range_text": detail.reference_range_text,
        "observed_date": (
            None if detail.observed_date is None else detail.observed_date.isoformat()
        ),
        "source_flag_text": detail.source_flag_text,
        "note": detail.note,
    }


def _canonical_record_dto(record: CanonicalRecord, candidate: CandidateFact) -> dict[str, object]:
    return {
        "canonical_record_id": record.id,
        "person_id": record.person_id,
        "candidate_id": record.candidate_id,
        "source_id": record.source_id,
        "fact_type": record.fact_type,
        "confirmed_at": isoformat_utc(record.confirmed_at),
        "is_active": record.is_active,
        "superseded_by_record_id": record.superseded_by_record_id,
        "provenance_locator": candidate.provenance_locator,
    }


def _canonical_medication_detail_dto(record: CanonicalRecord) -> dict[str, object]:
    detail = record.detail
    assert isinstance(detail, MedicationCandidateDetail)
    return {
        "record_id": record.id,
        "display_name": detail.display_name,
        "normalized_name": detail.normalized_name,
        "schedule_text": detail.schedule_text,
        "note": detail.note,
    }


def _canonical_condition_detail_dto(record: CanonicalRecord) -> dict[str, object]:
    detail = record.detail
    assert isinstance(detail, ConditionCandidateDetail)
    return {
        "record_id": record.id,
        "display_name": detail.display_name,
        "normalized_name": detail.normalized_name,
        "status_text": detail.status_text,
        "onset_date": (None if detail.onset_date is None else detail.onset_date.isoformat()),
        "note": detail.note,
    }


def _canonical_lab_detail_dto(record: CanonicalRecord) -> dict[str, object]:
    detail = record.detail
    assert isinstance(detail, LabCandidateDetail)
    return {
        "record_id": record.id,
        "test_name": detail.test_name,
        "normalized_test_name": detail.normalized_test_name,
        "result_text": detail.result_text,
        "unit_text": detail.unit_text,
        "reference_range_text": detail.reference_range_text,
        "observed_date": (
            None if detail.observed_date is None else detail.observed_date.isoformat()
        ),
        "source_flag_text": detail.source_flag_text,
        "note": detail.note,
    }


def _timeline_event_dto(event: TimelineEvent) -> dict[str, object]:
    return {
        "timeline_event_id": event.id,
        "person_id": event.person_id,
        "canonical_record_id": event.canonical_record_id,
        "source_id": event.source_id,
        "fact_type": event.fact_type,
        "event_type": event.event_type,
        "event_at": isoformat_utc(event.event_at),
        "title": event.title,
    }


def _visit_dto(visit: Visit) -> dict[str, object]:
    return {
        "visit_id": visit.visit_id,
        "person_id": visit.person_id,
        "title": visit.title,
        "specialist": visit.specialist,
        "scheduled_date": (
            None if visit.scheduled_date is None else visit.scheduled_date.isoformat()
        ),
        "created_at": isoformat_utc(visit.created_at),
        "updated_at": isoformat_utc(visit.updated_at),
    }


def _question_dto(question: VisitQuestion) -> dict[str, object]:
    return {
        "question_id": question.question_id,
        "visit_id": question.visit_id,
        "question_text": question.question_text,
        "position": question.position,
        "created_at": isoformat_utc(question.created_at),
        "updated_at": isoformat_utc(question.updated_at),
    }


def _brief_dto(
    brief: PersistedVisitBrief,
    revisions: list[PersistedVisitBriefRevision],
) -> dict[str, object]:
    return {
        "brief_id": brief.brief_id,
        "visit_id": brief.visit_id,
        "current_revision_id": brief.current_revision_id,
        "current_revision_number": brief.current_revision_number,
        "created_at": isoformat_utc(brief.created_at),
        "updated_at": isoformat_utc(brief.updated_at),
        "revision_numbers": [revision.revision_number for revision in revisions],
    }


def _revision_dto(revision: PersistedVisitBriefRevision) -> dict[str, object]:
    return {
        "revision_id": revision.revision_id,
        "brief_id": revision.brief_id,
        "revision_number": revision.revision_number,
        "origin": revision.origin,
        "parent_revision_id": revision.parent_revision_id,
        "content_schema_version": revision.content_schema_version,
        "render_version": revision.render_version,
        "content": revision.content,
        "rendered_markdown": revision.rendered_markdown,
        "content_hash": revision.content_hash,
        "created_at": isoformat_utc(revision.created_at),
    }


def _selection_dto(
    revision_id: str,
    selection: VisitBriefEvidenceSelection,
) -> dict[str, object]:
    return {
        "revision_id": revision_id,
        "canonical_record_id": selection.canonical_record_id,
        "source_id": selection.source_id,
        "position": selection.position,
        "snapshot": selection.snapshot,
    }


def _family_dto(row: Any) -> dict[str, object]:
    return {
        "family_id": str(row["family_id"]),
        "display_name": str(row["display_name"]),
        "created_by_actor_id": str(row["created_by_actor_id"]),
        "created_at": str(row["created_at"]),
        "is_archived": bool(row["is_archived"]),
        "archived_at": row["archived_at"],
        "archived_by_actor_id": row["archived_by_actor_id"],
    }


def _membership_dto(row: Any) -> dict[str, object]:
    return {
        "membership_id": str(row["membership_id"]),
        "family_id": str(row["family_id"]),
        "person_id": str(row["person_id"]),
        "created_by_actor_id": str(row["created_by_actor_id"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
        "ended_at": row["ended_at"],
        "ended_by_actor_id": row["ended_by_actor_id"],
    }


def _relationship_dto(row: Any) -> dict[str, object]:
    return {
        "relationship_id": str(row["relationship_id"]),
        "family_id": str(row["family_id"]),
        "person_id": str(row["person_id"]),
        "related_person_id": str(row["related_person_id"]),
        "relationship_type": str(row["relationship_type"]),
        "created_by_actor_id": str(row["created_by_actor_id"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
        "ended_at": row["ended_at"],
        "ended_by_actor_id": row["ended_by_actor_id"],
    }


def _consent_dto(row: Any) -> dict[str, object]:
    return {
        "consent_event_id": str(row["consent_event_id"]),
        "event_type": str(row["event_type"]),
        "acting_owner_actor_id": row["acting_owner_actor_id"],
        "recipient_actor_id": str(row["recipient_actor_id"]),
        "person_id": str(row["person_id"]),
        "role": str(row["role"]),
        "scopes": _stored_scope_list(row["scopes_json"]),
        "reason_code": str(row["reason_code"]),
        "created_at": str(row["created_at"]),
    }


def _assignment_dto(row: Any) -> dict[str, object]:
    return {
        "assignment_id": str(row["assignment_id"]),
        "actor_id": str(row["actor_id"]),
        "person_id": str(row["person_id"]),
        "role": str(row["role"]),
        "scopes": _stored_scope_list(row["scopes_json"]),
        "consent_event_id": str(row["consent_event_id"]),
        "granted_by_actor_id": str(row["granted_by_actor_id"]),
        "is_active": bool(row["is_active"]),
        "granted_at": str(row["granted_at"]),
        "revoked_at": row["revoked_at"],
        "revoked_by_actor_id": row["revoked_by_actor_id"],
        "revision_of_assignment_id": row["revision_of_assignment_id"],
    }


def _actor_dto(row: Any) -> dict[str, object]:
    return {
        "actor_id": str(row["actor_id"]),
        "display_name": str(row["display_name"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
    }


def _stored_scope_list(value: object) -> list[str]:
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise IntegrityStorageError("export access scopes are invalid") from exc
    if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
        raise IntegrityStorageError("export access scopes are invalid")
    return sorted(decoded)


def _relevant_actor_ids(*collections: list[dict[str, object]]) -> set[str]:
    actor_fields = {
        "actor_id",
        "created_by_actor_id",
        "ended_by_actor_id",
        "archived_by_actor_id",
        "acting_owner_actor_id",
        "recipient_actor_id",
        "granted_by_actor_id",
        "revoked_by_actor_id",
    }
    return {
        value
        for collection in collections
        for item in collection
        for field, raw_value in item.items()
        if field in actor_fields
        for value in [raw_value]
        if isinstance(value, str) and value
    }
