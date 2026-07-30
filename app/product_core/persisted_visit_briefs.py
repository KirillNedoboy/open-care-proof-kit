from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.product_core.errors import (
    SourceCorruptionError,
    VisitBriefAlreadyExistsError,
    VisitBriefConflictError,
    VisitBriefIntegrityError,
    VisitBriefNotFoundError,
    VisitBriefRevisionNotFoundError,
    VisitBriefValidationError,
    VisitNotFoundError,
)
from app.product_core.models import (
    CanonicalMedicationRecord,
    PersistedVisitBrief,
    PersistedVisitBriefRevision,
    Source,
    TimelineEvent,
    Visit,
    VisitBriefAuditEvent,
    VisitBriefEvidenceSelection,
    VisitBriefStaleness,
    VisitQuestion,
    ensure_utc_datetime,
    isoformat_utc,
)
from app.product_core.services import Clock, IdFactory, default_clock, default_id_factory
from app.product_core.sqlite import SQLiteDatabase, UnitOfWork

CONTENT_SCHEMA_VERSION = 1
RENDER_VERSION = 1
MAX_PREPARATION_NOTES_LENGTH = 2_000
SourceReader = Callable[[Source], bytes]


class PersistedVisitBriefService:
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

    def initialize(self, visit_id: str) -> PersistedVisitBrief:
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            if uow.visits.get(visit_id) is None:
                raise VisitNotFoundError(f"visit not found: {visit_id}")
            if uow.visit_briefs.get_by_visit(visit_id) is not None:
                raise VisitBriefAlreadyExistsError(f"visit brief already exists: {visit_id}")
            brief = PersistedVisitBrief(
                brief_id=self.id_factory(),
                visit_id=visit_id,
                created_at=now,
                updated_at=now,
            )
            uow.visit_briefs.insert(brief)
            self._audit(
                uow,
                visit_id=visit_id,
                brief_id=brief.brief_id,
                revision_number=None,
                action="initialize",
                resource_ids=[visit_id, brief.brief_id],
                outcome="succeeded",
                reason_code=None,
                now=now,
            )
        return brief

    def get(self, visit_id: str) -> PersistedVisitBrief:
        with self.database.uow() as uow:
            if uow.visits.get(visit_id) is None:
                raise VisitNotFoundError(f"visit not found: {visit_id}")
            brief = uow.visit_briefs.get_by_visit(visit_id)
        if brief is None:
            raise VisitBriefNotFoundError(f"visit brief not found: {visit_id}")
        return brief

    def list_revisions(self, visit_id: str) -> list[PersistedVisitBriefRevision]:
        brief = self.get(visit_id)
        with self.database.uow() as uow:
            revisions = uow.visit_brief_revisions.list_for_brief(brief.brief_id)
        for revision in revisions:
            verify_persisted_visit_brief_revision(revision)
        return revisions

    def get_revision(
        self,
        visit_id: str,
        revision_number: int,
    ) -> PersistedVisitBriefRevision:
        brief = self.get(visit_id)
        with self.database.uow() as uow:
            revision = uow.visit_brief_revisions.get_by_number(brief.brief_id, revision_number)
        if revision is None:
            raise VisitBriefRevisionNotFoundError(
                f"visit brief revision not found: {revision_number}"
            )
        verify_persisted_visit_brief_revision(revision)
        return revision

    def list_eligible_evidence(self, visit_id: str) -> list[dict[str, object]]:
        with self.database.uow() as uow:
            visit = self._visit_or_raise(uow, visit_id)
            records = uow.canonical_records.list_active_for_person(visit.person_id)
            return [
                self._evidence_preview(record, self._source_or_raise(uow, record.source_id))
                for record in records
            ]

    def validate_evidence_selection(
        self,
        visit_id: str,
        selected_record_ids: list[str],
    ) -> dict[str, object]:
        with self.database.uow() as uow:
            visit = self._visit_or_raise(uow, visit_id)
            selections = self._validated_selections(uow, visit, selected_record_ids)
        return {
            "valid": True,
            "selection_fingerprint": _canonical_hash(
                [selection.snapshot["fingerprint"] for selection in selections]
            ),
            "evidence": [selection.model_dump() for selection in selections],
        }

    def generate(
        self,
        visit_id: str,
        *,
        selected_record_ids: list[str],
        expected_current_revision_number: int | None,
    ) -> PersistedVisitBriefRevision:
        now = ensure_utc_datetime(self.clock())
        conflict = False
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            visit = self._visit_or_raise(uow, visit_id)
            brief = self._brief_or_raise(uow, visit_id)
            if brief.current_revision_number != expected_current_revision_number:
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=expected_current_revision_number,
                    action="concurrency_conflict",
                    resource_ids=[visit_id, brief.brief_id],
                    outcome="rejected",
                    reason_code="expected_current_revision_mismatch",
                    now=now,
                )
                conflict = True
            else:
                selections = self._validated_selections(uow, visit, selected_record_ids)
                revision_number = (brief.current_revision_number or 0) + 1
                parent = (
                    None
                    if brief.current_revision_number is None
                    else uow.visit_brief_revisions.get_by_number(
                        brief.brief_id, brief.current_revision_number
                    )
                )
                origin = "deterministic_generation" if parent is None else "regeneration"
                content = self._build_content(
                    uow,
                    visit=visit,
                    selections=selections,
                    preparation_notes="",
                    revision_number=revision_number,
                    origin=origin,
                    now=now,
                )
                revision = self._new_revision(
                    brief_id=brief.brief_id,
                    revision_number=revision_number,
                    origin=origin,
                    parent_revision_id=None if parent is None else parent.revision_id,
                    content=content,
                    now=now,
                )
                uow.visit_brief_revisions.insert(revision)
                uow.visit_brief_evidence.insert_many(selections, revision.revision_id)
                uow.visit_briefs.update_current(brief.brief_id, revision.revision_id, now)
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=revision.revision_number,
                    action=origin,
                    resource_ids=[visit_id, brief.brief_id, revision.revision_id],
                    outcome="succeeded",
                    reason_code=None,
                    now=now,
                )
        if conflict:
            raise VisitBriefConflictError("expected current revision does not match")
        return revision

    def save_user_edit(
        self,
        visit_id: str,
        *,
        preparation_notes: str,
        expected_current_revision_number: int,
    ) -> PersistedVisitBriefRevision:
        notes = _preparation_notes(preparation_notes)
        now = ensure_utc_datetime(self.clock())
        conflict = False
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            brief = self._brief_or_raise(uow, visit_id)
            if brief.current_revision_number != expected_current_revision_number:
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=expected_current_revision_number,
                    action="concurrency_conflict",
                    resource_ids=[visit_id, brief.brief_id],
                    outcome="rejected",
                    reason_code="expected_current_revision_mismatch",
                    now=now,
                )
                conflict = True
            else:
                parent = uow.visit_brief_revisions.get_by_number(
                    brief.brief_id, expected_current_revision_number
                )
                if parent is None:
                    raise VisitBriefRevisionNotFoundError("current revision not found")
                verify_persisted_visit_brief_revision(parent)
                content = dict(parent.content)
                content["preparation_notes"] = notes
                content["revision"] = {
                    "revision_number": expected_current_revision_number + 1,
                    "origin": "user_edit",
                    "generated_at": isoformat_utc(now),
                }
                revision = self._new_revision(
                    brief_id=brief.brief_id,
                    revision_number=expected_current_revision_number + 1,
                    origin="user_edit",
                    parent_revision_id=parent.revision_id,
                    content=content,
                    now=now,
                )
                selections = uow.visit_brief_evidence.list_for_revision(parent.revision_id)
                uow.visit_brief_revisions.insert(revision)
                uow.visit_brief_evidence.insert_many(selections, revision.revision_id)
                uow.visit_briefs.update_current(brief.brief_id, revision.revision_id, now)
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=revision.revision_number,
                    action="user_edit",
                    resource_ids=[visit_id, brief.brief_id, revision.revision_id],
                    outcome="succeeded",
                    reason_code=None,
                    now=now,
                )
        if conflict:
            raise VisitBriefConflictError("expected current revision does not match")
        return revision

    def restore(
        self,
        visit_id: str,
        *,
        revision_number: int,
        expected_current_revision_number: int,
    ) -> PersistedVisitBrief:
        now = ensure_utc_datetime(self.clock())
        conflict = False
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            brief = self._brief_or_raise(uow, visit_id)
            if brief.current_revision_number != expected_current_revision_number:
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=expected_current_revision_number,
                    action="concurrency_conflict",
                    resource_ids=[visit_id, brief.brief_id],
                    outcome="rejected",
                    reason_code="expected_current_revision_mismatch",
                    now=now,
                )
                conflict = True
            else:
                target = uow.visit_brief_revisions.get_by_number(brief.brief_id, revision_number)
                if target is None:
                    raise VisitBriefRevisionNotFoundError(
                        f"visit brief revision not found: {revision_number}"
                    )
                verify_persisted_visit_brief_revision(target)
                uow.visit_briefs.update_current(brief.brief_id, target.revision_id, now)
                self._audit(
                    uow,
                    visit_id=visit_id,
                    brief_id=brief.brief_id,
                    revision_number=target.revision_number,
                    action="restore",
                    resource_ids=[visit_id, brief.brief_id, target.revision_id],
                    outcome="succeeded",
                    reason_code=None,
                    now=now,
                )
        if conflict:
            raise VisitBriefConflictError("expected current revision does not match")
        return self.get(visit_id)

    def export_current(self, visit_id: str) -> tuple[str, int]:
        now = ensure_utc_datetime(self.clock())
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            brief = self._brief_or_raise(uow, visit_id)
            if brief.current_revision_number is None:
                raise VisitBriefValidationError("visit brief has no current revision")
            revision = uow.visit_brief_revisions.get_by_number(
                brief.brief_id, brief.current_revision_number
            )
            if revision is None:
                raise VisitBriefRevisionNotFoundError("current revision not found")
            verify_persisted_visit_brief_revision(revision)
            self._audit(
                uow,
                visit_id=visit_id,
                brief_id=brief.brief_id,
                revision_number=revision.revision_number,
                action="export",
                resource_ids=[visit_id, brief.brief_id, revision.revision_id],
                outcome="succeeded",
                reason_code=None,
                now=now,
            )
            return revision.rendered_markdown, revision.revision_number

    def staleness(self, visit_id: str, revision_number: int) -> VisitBriefStaleness:
        revision = self.get_revision(visit_id, revision_number)
        unavailable: list[str] = []
        stale: list[str] = []
        with self.database.uow() as uow:
            visit = self._visit_or_raise(uow, visit_id)
            snapshot_visit = revision.content["visit"]
            if snapshot_visit["updated_at"] != isoformat_utc(visit.updated_at):
                stale.append("visit_changed")
            questions = uow.visit_questions.list_for_visit(visit_id)
            if _questions_fingerprint(questions) != revision.content["questions_fingerprint"]:
                stale.append("questions_changed")
            selections = uow.visit_brief_evidence.list_for_revision(revision.revision_id)
            if (
                _canonical_hash([item.snapshot["fingerprint"] for item in selections])
                != revision.content["evidence_selection_fingerprint"]
            ):
                stale.append("selection_changed")
            current_events = uow.timeline_events.list_for_person(visit.person_id)
            for selection in selections:
                record = uow.canonical_records.get(selection.canonical_record_id)
                source = uow.sources.get(selection.source_id)
                if record is None or source is None:
                    unavailable.append("evidence_missing")
                    continue
                if record.person_id != visit.person_id or source.person_id != visit.person_id:
                    unavailable.append("evidence_foreign")
                    continue
                if not record.is_active:
                    unavailable.append("evidence_inactive")
                    continue
                try:
                    self._verify_source(source)
                except SourceCorruptionError:
                    unavailable.append("source_unavailable")
                    continue
                preview = self._evidence_preview(record, source)
                if preview["fingerprint"] != selection.snapshot["fingerprint"]:
                    stale.append("medication_or_source_changed")
                event_fingerprint = _canonical_hash(
                    [
                        _timeline_snapshot(event)
                        for event in current_events
                        if event.canonical_record_id == record.id
                    ]
                )
                saved_event_fingerprint = selection.snapshot.get("timeline_fingerprint")
                if event_fingerprint != saved_event_fingerprint:
                    stale.append("timeline_changed")
        if unavailable:
            return VisitBriefStaleness(state="unavailable", reasons=sorted(set(unavailable)))
        if stale:
            return VisitBriefStaleness(state="stale", reasons=sorted(set(stale)))
        return VisitBriefStaleness(state="current")

    def _build_content(
        self,
        uow: UnitOfWork,
        *,
        visit: Visit,
        selections: list[VisitBriefEvidenceSelection],
        preparation_notes: str,
        revision_number: int,
        origin: str,
        now: datetime,
    ) -> dict[str, object]:
        # UnitOfWork stays structural in the public API; these repositories are
        # intentionally accessed through its concrete transaction-bound surface.
        questions = uow.visit_questions.list_for_visit(visit.visit_id)
        events = uow.timeline_events.list_for_person(visit.person_id)
        selected_ids = {selection.canonical_record_id for selection in selections}
        derived_events = [
            _timeline_snapshot(event)
            for event in events
            if event.canonical_record_id in selected_ids
        ]
        derived_events.sort(key=lambda item: (item["event_at"], item["event_id"]))
        events_by_record: dict[str, list[dict[str, object]]] = {}
        for event in derived_events:
            events_by_record.setdefault(str(event["canonical_record_id"]), []).append(event)
        enriched_selections = [
            selection.model_copy(
                update={
                    "snapshot": {
                        **selection.snapshot,
                        "timeline_fingerprint": _canonical_hash(
                            events_by_record.get(selection.canonical_record_id, [])
                        ),
                    }
                }
            )
            for selection in selections
        ]
        selections[:] = enriched_selections
        medications = [selection.snapshot for selection in selections]
        return {
            "content_schema_version": CONTENT_SCHEMA_VERSION,
            "visit": {
                "visit_id": visit.visit_id,
                "title": visit.title,
                "specialist": visit.specialist,
                "scheduled_date": None
                if visit.scheduled_date is None
                else visit.scheduled_date.isoformat(),
                "updated_at": isoformat_utc(visit.updated_at),
            },
            "questions": [_question_snapshot(question) for question in questions],
            "questions_fingerprint": _questions_fingerprint(questions),
            "medications": medications,
            "timeline_events": derived_events,
            "source_references": list(
                dict.fromkeys(selection.source_id for selection in selections)
            ),
            "evidence_selection_fingerprint": _canonical_hash(
                [selection.snapshot["fingerprint"] for selection in selections]
            ),
            "preparation_notes": preparation_notes,
            "unresolved": (
                ["No confirmed medication evidence was selected."] if not selections else []
            ),
            "revision": {
                "revision_number": revision_number,
                "origin": origin,
                "generated_at": isoformat_utc(now),
            },
            "boundary": (
                "This brief contains recorded preparation context only; it is not medical advice."
            ),
        }

    def _new_revision(
        self,
        *,
        brief_id: str,
        revision_number: int,
        origin: str,
        parent_revision_id: str | None,
        content: dict[str, object],
        now: datetime,
    ) -> PersistedVisitBriefRevision:
        markdown = _render_markdown(content)
        content_hash = _content_hash(content, markdown)
        return PersistedVisitBriefRevision(
            revision_id=self.id_factory(),
            brief_id=brief_id,
            revision_number=revision_number,
            origin=origin,  # type: ignore[arg-type]
            parent_revision_id=parent_revision_id,
            content_schema_version=CONTENT_SCHEMA_VERSION,
            render_version=RENDER_VERSION,
            content=content,
            rendered_markdown=markdown,
            content_hash=content_hash,
            created_at=now,
        )

    def _validated_selections(
        self,
        uow: UnitOfWork,
        visit: Visit,
        selected_record_ids: list[str],
    ) -> list[VisitBriefEvidenceSelection]:
        if len(selected_record_ids) != len(set(selected_record_ids)):
            raise VisitBriefValidationError("selected canonical record IDs must be unique")
        selections: list[VisitBriefEvidenceSelection] = []
        for record_id in selected_record_ids:
            record = uow.canonical_records.get(record_id)
            if record is None:
                raise VisitBriefValidationError("selected canonical record is unavailable")
            if record.person_id != visit.person_id:
                raise VisitBriefValidationError(
                    "selected canonical record belongs to another person"
                )
            if not record.is_active:
                raise VisitBriefValidationError("selected canonical record is inactive")
            source = self._source_or_raise(uow, record.source_id)
            if source.person_id != visit.person_id:
                raise VisitBriefValidationError("selected source belongs to another person")
            try:
                self._verify_source(source)
            except SourceCorruptionError as exc:
                raise VisitBriefValidationError("selected source is unavailable") from exc
            selections.append(
                VisitBriefEvidenceSelection(
                    canonical_record_id=record.id,
                    source_id=source.id,
                    position=len(selections),
                    snapshot=self._evidence_preview(record, source),
                )
            )
        selections.sort(key=lambda item: (item.snapshot["confirmed_at"], item.canonical_record_id))
        return [
            selection.model_copy(update={"position": index})
            for index, selection in enumerate(selections)
        ]

    @staticmethod
    def _visit_or_raise(uow: UnitOfWork, visit_id: str) -> Visit:
        visit = uow.visits.get(visit_id)
        if visit is None:
            raise VisitNotFoundError(f"visit not found: {visit_id}")
        return visit

    @staticmethod
    def _brief_or_raise(uow: UnitOfWork, visit_id: str) -> PersistedVisitBrief:
        brief = uow.visit_briefs.get_by_visit(visit_id)
        if brief is None:
            raise VisitBriefNotFoundError(f"visit brief not found: {visit_id}")
        return brief

    @staticmethod
    def _source_or_raise(uow: UnitOfWork, source_id: str) -> Source:
        source = uow.sources.get(source_id)
        if source is None:
            raise VisitBriefValidationError("selected source is unavailable")
        return source

    def _verify_source(self, source: Source) -> None:
        if self.source_reader is not None:
            self.source_reader(source)

    @staticmethod
    def _evidence_preview(record: CanonicalMedicationRecord, source: Source) -> dict[str, object]:
        source_snapshot = {
            "source_id": source.id,
            "source_type": source.source_type,
            "content_hash": source.content_hash,
            "provenance_method": source.provenance.get("entry_method", source.source_type),
        }
        preview: dict[str, object] = {
            "canonical_record_id": record.id,
            "record_type": "confirmed_medication",
            "display_name": record.display_name,
            "schedule_text": record.schedule_text,
            "note": record.note,
            "confirmed_at": isoformat_utc(record.confirmed_at),
            "confirmation_status": "confirmed",
            "source": source_snapshot,
        }
        preview["fingerprint"] = _canonical_hash(preview)
        return preview

    def _audit(
        self,
        uow: UnitOfWork,
        *,
        visit_id: str,
        brief_id: str | None,
        revision_number: int | None,
        action: str,
        resource_ids: list[str],
        outcome: str,
        reason_code: str | None,
        now: datetime,
    ) -> None:
        event = VisitBriefAuditEvent(
            audit_event_id=self.id_factory(),
            visit_id=visit_id,
            brief_id=brief_id,
            revision_number=revision_number,
            action=action,  # type: ignore[arg-type]
            involved_resource_ids=resource_ids,
            outcome=outcome,  # type: ignore[arg-type]
            reason_code=reason_code,
            created_at=now,
        )
        uow.visit_brief_audit.insert(event)


def verify_persisted_visit_brief_revision(
    revision: PersistedVisitBriefRevision,
) -> None:
    """Verify a persisted revision before it is rendered, exported, or reused."""
    if revision.content_schema_version != CONTENT_SCHEMA_VERSION:
        raise VisitBriefIntegrityError("unsupported visit brief content schema version")
    if revision.render_version != RENDER_VERSION:
        raise VisitBriefIntegrityError("unsupported visit brief render version")
    if _content_hash(revision.content, revision.rendered_markdown) != revision.content_hash:
        raise VisitBriefIntegrityError("visit brief content integrity failed")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _content_hash(content: dict[str, object], markdown: str) -> str:
    return _canonical_hash(
        {
            "content_schema_version": CONTENT_SCHEMA_VERSION,
            "render_version": RENDER_VERSION,
            "content": content,
            "rendered_markdown": markdown,
        }
    )


def _question_snapshot(question: VisitQuestion) -> dict[str, object]:
    return {
        "question_id": question.question_id,
        "position": question.position,
        "question_text": question.question_text,
        "updated_at": isoformat_utc(question.updated_at),
        "text_hash": _canonical_hash(question.question_text),
    }


def _questions_fingerprint(questions: list[VisitQuestion]) -> str:
    return _canonical_hash([_question_snapshot(question) for question in questions])


def _timeline_snapshot(event: TimelineEvent) -> dict[str, object]:
    return {
        "event_id": event.id,
        "canonical_record_id": event.canonical_record_id,
        "source_id": event.source_id,
        "event_type": event.event_type,
        "event_at": isoformat_utc(event.event_at),
        "title": event.title,
    }


def _preparation_notes(value: str) -> str:
    if not isinstance(value, str):
        raise VisitBriefValidationError("preparation_notes must be text")
    if len(value) > MAX_PREPARATION_NOTES_LENGTH:
        raise VisitBriefValidationError("preparation_notes is too long")
    if any(
        unicodedata.category(character) == "Cc" and character not in {"\n", "\r", "\t"}
        for character in value
    ):
        raise VisitBriefValidationError("preparation_notes must not contain control characters")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _render_markdown(content: dict[str, Any]) -> str:
    visit = content["visit"]
    questions = content["questions"]
    medications = content["medications"]
    events = content["timeline_events"]
    notes = content["preparation_notes"]
    lines = [
        "# Visit Brief",
        "",
        f"- Title: {visit['title']}",
        f"- Specialist: {visit['specialist'] or 'Unknown'}",
        f"- Scheduled date: {visit['scheduled_date'] or 'Unknown'}",
        f"- Generated at: {content['revision']['generated_at']}",
        "",
        "## Confirmed medications",
        "",
    ]
    if medications:
        for medication in medications:
            lines.extend(
                [
                    f"### {medication['display_name']}",
                    f"- Schedule: {medication['schedule_text'] or 'Unknown'}",
                    f"- Note: {medication['note'] or 'Unknown'}",
                    f"- Source: {medication['source']['source_id']}",
                    "",
                ]
            )
    else:
        lines.extend(["- No confirmed medication evidence was selected.", ""])
    lines.extend(["## Timeline changes", ""])
    if events:
        for event in events:
            lines.append(f"- {event['event_at']}: {event['title']} (Source: {event['source_id']})")
    else:
        lines.append("- No related timeline events are available.")
    lines.extend(["", "## Visit questions", ""])
    if questions:
        for question in questions:
            lines.append(f"- {question['question_text']}")
    else:
        lines.append("- No questions have been added for this visit.")
    lines.extend(["", "## Preparation notes", "", notes or "- No preparation notes.", ""])
    lines.extend(["## Boundary", "", f"- {content['boundary']}", ""])
    return "\n".join(lines)
