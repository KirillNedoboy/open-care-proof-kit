from __future__ import annotations

from app.product_core.errors import PersonNotFoundError, SelectionError
from app.product_core.models import (
    CanonicalMedicationRecord,
    VisitBrief,
    VisitBriefMedication,
    VisitBriefRequest,
    isoformat_utc,
)
from app.product_core.sqlite import SQLiteDatabase


class VisitBriefService:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def generate(self, request: VisitBriefRequest) -> VisitBrief:
        selected_ids = request.selected_record_ids or []
        if len(selected_ids) != len(set(selected_ids)):
            raise SelectionError("selected canonical record IDs must be unique")

        with self.database.uow() as uow:
            if uow.people.get(request.person_id) is None:
                raise PersonNotFoundError(f"person not found: {request.person_id}")
            if selected_ids:
                records = []
                for record_id in selected_ids:
                    record = uow.canonical_records.get(record_id)
                    if record is None:
                        raise SelectionError(f"canonical record not found: {record_id}")
                    if record.person_id != request.person_id:
                        raise SelectionError(
                            f"canonical record belongs to another person: {record_id}"
                        )
                    if not record.is_active:
                        raise SelectionError(f"canonical record is inactive: {record_id}")
                    records.append(record)
                records.sort(key=lambda item: (item.confirmed_at, item.id))
            else:
                records = uow.canonical_records.list_active_for_person(
                    request.person_id, fact_type="medication"
                )

        medications = []
        for record in records:
            display_name = record.display_name
            assert display_name is not None  # medication records always carry a name
            medications.append(
                VisitBriefMedication(
                    id=record.id,
                    display_name=display_name,
                    schedule_text=record.schedule_text,
                    note=record.note,
                    source_id=record.source_id,
                )
            )
        source_references = list(dict.fromkeys(record.source_id for record in records))
        markdown = _render_markdown(request, records)
        return VisitBrief(
            person_id=request.person_id,
            visit_title=request.visit_title,
            visit_purpose=request.visit_purpose,
            scheduled_date=request.scheduled_date,
            generated_at=request.generated_at,
            records=medications,
            source_references=source_references,
            markdown=markdown,
        )


def _render_markdown(
    request: VisitBriefRequest,
    records: list[CanonicalMedicationRecord],
) -> str:
    scheduled_date = request.scheduled_date or "Unknown"
    lines = [
        "# Visit Brief",
        "",
        f"- Title: {request.visit_title}",
        f"- Purpose: {request.visit_purpose}",
        f"- Scheduled date: {scheduled_date}",
        f"- Generated at: {isoformat_utc(request.generated_at)}",
        "",
        "## Active medications",
        "",
    ]
    if records:
        for record in records:
            lines.extend(
                [
                    f"### {record.display_name}",
                    f"- Schedule: {record.schedule_text or 'Unknown'}",
                    f"- Note: {record.note or 'Unknown'}",
                    f"- Source: {record.source_id}",
                    "",
                ]
            )
        lines.extend(
            [
                "## Empty or unknown sections",
                "",
                "- No additional medication facts are selected.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "- No active medication records are available.",
                "",
                "## Empty or unknown sections",
                "",
                "- No additional medication facts are selected.",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- This brief contains user-confirmed recorded information only.",
            "",
        ]
    )
    return "\n".join(lines)
