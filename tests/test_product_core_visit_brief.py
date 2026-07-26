from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.product_core.errors import SelectionError
from app.product_core.models import VisitBriefRequest
from app.product_core.services import MedicationLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visit_brief import VisitBriefService


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self, *values: str) -> None:
        self.values = iter(values)

    def __call__(self) -> str:
        return next(self.values)


def setup_records(
    tmp_path: Path,
) -> tuple[SQLiteDatabase, MedicationLifecycleService, VisitBriefService, list]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    clock = FixedClock(datetime(2026, 7, 26, 10, tzinfo=UTC))
    ids = SequenceIds(
        "source-1",
        "candidate-1",
        "canonical-1",
        "event-1",
        "source-2",
        "candidate-2",
        "canonical-2",
        "event-2",
        "source-3",
        "candidate-3",
        "canonical-3",
        "event-3",
    )
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    lifecycle = MedicationLifecycleService(database, clock=clock, id_factory=ids)
    records = []
    for name in ["Aspirin", "Ibuprofen", "Other"]:
        person_id = "person-1" if name != "Other" else "person-2"
        source = sources.register_manual_entry(person_id, name)
        candidate = lifecycle.create_candidate(
            person_id=person_id,
            source_id=source.id,
            display_name=name,
            schedule_text=None if name == "Aspirin" else "evening",
            note=None,
        )
        records.append(lifecycle.confirm(candidate.id))
    return database, lifecycle, VisitBriefService(database), records


def test_visit_brief_is_exact_and_non_advisory(tmp_path: Path) -> None:
    _, _, brief_service, records = setup_records(tmp_path)

    brief = brief_service.generate(
        VisitBriefRequest(
            person_id="person-1",
            visit_title="Next visit",
            visit_purpose="Review current records",
            generated_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
        )
    )

    assert brief.records[0].display_name == "Aspirin"
    assert brief.records[1].display_name == "Ibuprofen"
    assert brief.source_references == ["source-1", "source-2"]
    assert brief.markdown == (
        "# Visit Brief\n"
        "\n"
        "- Title: Next visit\n"
        "- Purpose: Review current records\n"
        "- Scheduled date: Unknown\n"
        "- Generated at: 2026-07-26T12:00:00+00:00\n"
        "\n"
        "## Active medications\n"
        "\n"
        "### Aspirin\n"
        "- Schedule: Unknown\n"
        "- Note: Unknown\n"
        "- Source: source-1\n"
        "\n"
        "### Ibuprofen\n"
        "- Schedule: evening\n"
        "- Note: Unknown\n"
        "- Source: source-2\n"
        "\n"
        "## Empty or unknown sections\n"
        "\n"
        "- No additional medication facts are selected.\n"
        "\n"
        "## Boundary\n"
        "\n"
        "- This brief contains user-confirmed recorded information only.\n"
    )
    assert "recommend" not in brief.markdown.lower()
    assert "dosage" not in brief.markdown.lower()
    assert records[2].person_id == "person-2"


def test_visit_brief_selection_is_validated_and_sorted_independently_of_input_order(
    tmp_path: Path,
) -> None:
    _, _, brief_service, records = setup_records(tmp_path)
    request = VisitBriefRequest(
        person_id="person-1",
        visit_title="Next visit",
        visit_purpose="Review",
        generated_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
        selected_record_ids=[records[1].id, records[0].id],
    )

    brief = brief_service.generate(request)

    assert [record.id for record in brief.records] == [records[0].id, records[1].id]
    for invalid_ids in ([records[0].id, records[0].id], ["missing"], [records[2].id]):
        invalid_request = request.model_copy(update={"selected_record_ids": invalid_ids})
        with pytest.raises(SelectionError):
            brief_service.generate(invalid_request)


def test_visit_brief_rejects_inactive_records_and_naive_generated_at(tmp_path: Path) -> None:
    database, _, brief_service, records = setup_records(tmp_path)
    with database.connect() as connection:
        connection.execute(
            "UPDATE canonical_medication_records SET is_active=0 WHERE id=?",
            (records[0].id,),
        )

    with pytest.raises(SelectionError):
        brief_service.generate(
            VisitBriefRequest(
                person_id="person-1",
                visit_title="Next visit",
                visit_purpose="Review",
                generated_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
                selected_record_ids=[records[0].id],
            )
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        VisitBriefRequest(
            person_id="person-1",
            visit_title="Next visit",
            visit_purpose="Review",
            generated_at=datetime(2026, 7, 26, 12),
        )
