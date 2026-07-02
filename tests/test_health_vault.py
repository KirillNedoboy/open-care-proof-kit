import json
from pathlib import Path

import pytest

from app.demo_pipeline import build_demo_briefing
from app.health_vault.loader import load_demo_family_vault, load_family_vault


def valid_family_vault() -> dict[str, object]:
    return {
        "dataset_id": "demo-family-vault",
        "version": "0.1.0",
        "demo_only": True,
        "synthetic": True,
        "family": {
            "id": "family-demo-01",
            "display_name": "Synthetic Demo Family",
            "synthetic": True,
        },
        "people": [
            {
                "id": "person-a",
                "display_name": "Demo Adult A",
                "role": "self",
                "synthetic": True,
                "notes": "Synthetic person record for demo only.",
            },
            {
                "id": "person-b",
                "display_name": "Demo Adult B",
                "role": "spouse",
                "synthetic": True,
                "notes": "Synthetic person record for demo only.",
            },
            {
                "id": "person-c",
                "display_name": "Demo Child C",
                "role": "child",
                "synthetic": True,
                "notes": "Synthetic person record for demo only.",
            },
        ],
        "relationships": [
            {
                "id": "rel-a-b",
                "person_id": "person-a",
                "related_person_id": "person-b",
                "relationship_type": "spouse",
            },
            {
                "id": "rel-a-c",
                "person_id": "person-a",
                "related_person_id": "person-c",
                "relationship_type": "child",
            },
        ],
        "document_sources": [
            {
                "id": "source-visit",
                "title": "Synthetic visit note",
                "source_type": "visit_note",
                "synthetic": True,
                "demo_only": True,
                "description": "Fabricated visit note for schema validation.",
            },
            {
                "id": "source-lab",
                "title": "Synthetic lab report",
                "source_type": "lab_report",
                "synthetic": True,
                "demo_only": True,
                "description": "Fabricated lab report for schema validation.",
            },
            {
                "id": "source-med",
                "title": "Synthetic medication record",
                "source_type": "medication_record",
                "synthetic": True,
                "demo_only": True,
                "description": "Fabricated medication list for schema validation.",
            },
        ],
        "conditions": [
            {
                "id": "condition-sleep",
                "person_id": "person-a",
                "name": "Sleep concern recorded by demo user",
                "status": "active",
                "description": "User-recorded context only; not an OpenCare diagnosis.",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "user_reported",
                        "note": "Recorded as a demo user concern.",
                    }
                ],
            },
            {
                "id": "condition-allergy",
                "person_id": "person-c",
                "name": "Seasonal allergy history recorded by demo user",
                "status": "historical",
                "description": "Demo-recorded context only; not an OpenCare diagnosis.",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "source_backed",
                        "note": "Mentioned in a synthetic visit note.",
                    }
                ],
            },
        ],
        "medications": [
            {
                "id": "med-a",
                "person_id": "person-a",
                "name": "sertraline",
                "status": "current",
                "reason_context": "Medication question recorded for clinician discussion.",
                "evidence": [
                    {
                        "source_id": "source-med",
                        "strength": "source_backed",
                        "note": "Listed in a synthetic medication record.",
                    }
                ],
            },
            {
                "id": "med-b",
                "person_id": "person-b",
                "name": "loratadine",
                "status": "past",
                "reason_context": "Past medication recorded as demo context.",
                "evidence": [
                    {
                        "source_id": "source-med",
                        "strength": "source_backed",
                        "note": "Listed in a synthetic medication record.",
                    }
                ],
            },
        ],
        "lab_results": [
            {
                "id": "lab-a1c",
                "person_id": "person-a",
                "name": "A1c",
                "result_text": "Within demo reference context",
                "collected_on": "2026-01-15",
                "evidence": [
                    {
                        "source_id": "source-lab",
                        "strength": "source_backed",
                        "note": "From a synthetic lab report.",
                    }
                ],
            },
            {
                "id": "lab-vit-d",
                "person_id": "person-b",
                "name": "Vitamin D",
                "result_text": "Flagged in synthetic record for follow-up discussion",
                "collected_on": "2026-02-12",
                "evidence": [
                    {
                        "source_id": "source-lab",
                        "strength": "source_backed",
                        "note": "From a synthetic lab report.",
                    }
                ],
            },
        ],
        "visits": [
            {
                "id": "visit-a",
                "person_id": "person-a",
                "visit_type": "primary care",
                "date": "2026-01-20",
                "summary": "Synthetic visit summary for organizing questions.",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "source_backed",
                        "note": "From a synthetic visit note.",
                    }
                ],
            },
            {
                "id": "visit-b",
                "person_id": "person-c",
                "visit_type": "pediatric check-in",
                "date": "2026-03-05",
                "summary": "Synthetic family context visit.",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "source_backed",
                        "note": "From a synthetic visit note.",
                    }
                ],
            },
        ],
        "timeline_events": [
            {
                "id": "event-1",
                "person_id": "person-a",
                "event_type": "visit",
                "date": "2026-01-20",
                "title": "Primary care visit",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "source_backed",
                        "note": "Timeline event from synthetic visit note.",
                    }
                ],
            },
            {
                "id": "event-2",
                "person_id": "person-a",
                "event_type": "lab",
                "date": "2026-01-15",
                "title": "A1c lab recorded",
                "evidence": [
                    {
                        "source_id": "source-lab",
                        "strength": "source_backed",
                        "note": "Timeline event from synthetic lab report.",
                    }
                ],
            },
            {
                "id": "event-3",
                "person_id": "person-b",
                "event_type": "lab",
                "date": "2026-02-12",
                "title": "Vitamin D lab recorded",
                "evidence": [
                    {
                        "source_id": "source-lab",
                        "strength": "source_backed",
                        "note": "Timeline event from synthetic lab report.",
                    }
                ],
            },
            {
                "id": "event-4",
                "person_id": "person-c",
                "event_type": "visit",
                "date": "2026-03-05",
                "title": "Pediatric check-in",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "source_backed",
                        "note": "Timeline event from synthetic visit note.",
                    }
                ],
            },
        ],
        "question_threads": [
            {
                "id": "question-a",
                "scope": "person",
                "person_id": "person-a",
                "status": "open",
                "question": "What should Demo Adult A discuss with a clinician about sleep notes?",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "user_reported",
                        "note": "Question grounded in a synthetic visit note.",
                    }
                ],
            },
            {
                "id": "question-family",
                "scope": "family",
                "person_id": None,
                "status": "needs_source",
                "question": "Which family records are still missing source documents?",
                "evidence": [
                    {
                        "source_id": "source-visit",
                        "strength": "inferred_from_demo_context",
                        "note": "Synthetic family organization question.",
                    }
                ],
            },
        ],
    }


def write_vault(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "family_vault.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_demo_family_vault_returns_typed_synthetic_dataset() -> None:
    vault = load_demo_family_vault()

    assert vault.demo_only is True
    assert vault.synthetic is True
    assert vault.family.synthetic is True
    assert len(vault.people) >= 3
    assert len(vault.relationships) >= 2
    assert len(vault.medications) >= 2
    assert len(vault.conditions) >= 2
    assert len(vault.lab_results) >= 2
    assert len(vault.visits) >= 2
    assert len(vault.timeline_events) >= 4
    assert len(vault.question_threads) >= 2
    assert len(vault.document_sources) >= 3


def test_person_ids_are_unique(tmp_path: Path) -> None:
    payload = valid_family_vault()
    people = payload["people"]
    assert isinstance(people, list)
    people[1] = people[0]

    with pytest.raises(ValueError, match="Duplicate id"):
        load_family_vault(write_vault(tmp_path, payload))


def test_relationships_must_reference_known_people(tmp_path: Path) -> None:
    payload = valid_family_vault()
    relationships = payload["relationships"]
    assert isinstance(relationships, list)
    relationships[0]["related_person_id"] = "missing-person"

    with pytest.raises(ValueError, match="unknown person"):
        load_family_vault(write_vault(tmp_path, payload))


def test_records_cannot_reference_unknown_people(tmp_path: Path) -> None:
    payload = valid_family_vault()
    medications = payload["medications"]
    assert isinstance(medications, list)
    medications[0]["person_id"] = "missing-person"

    with pytest.raises(ValueError, match="unknown person"):
        load_family_vault(write_vault(tmp_path, payload))


def test_evidence_must_reference_known_document_sources(tmp_path: Path) -> None:
    payload = valid_family_vault()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["evidence"][0]["source_id"] = "missing-source"

    with pytest.raises(ValueError, match="unknown source"):
        load_family_vault(write_vault(tmp_path, payload))


def test_important_records_without_provenance_fail(tmp_path: Path) -> None:
    payload = valid_family_vault()
    lab_results = payload["lab_results"]
    assert isinstance(lab_results, list)
    lab_results[0]["evidence"] = []

    with pytest.raises(ValueError, match="provenance"):
        load_family_vault(write_vault(tmp_path, payload))


def test_non_demo_dataset_fails(tmp_path: Path) -> None:
    payload = valid_family_vault()
    payload["demo_only"] = False

    with pytest.raises(ValueError, match="demo_only"):
        load_family_vault(write_vault(tmp_path, payload))


def test_non_synthetic_person_fails(tmp_path: Path) -> None:
    payload = valid_family_vault()
    people = payload["people"]
    assert isinstance(people, list)
    people[0]["synthetic"] = False

    with pytest.raises(ValueError, match="synthetic"):
        load_family_vault(write_vault(tmp_path, payload))


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "OpenCare diagnosis: major depression.",
        "You should increase the dose.",
        "Stop taking sertraline now.",
        "Start taking aspirin tomorrow.",
        "OpenCare recommends choosing medication A over medication B.",
        "This is clinical decision support for treatment.",
        "This contains real patient data.",
    ],
)
def test_unsafe_medical_claim_text_fails(tmp_path: Path, unsafe_text: str) -> None:
    payload = valid_family_vault()
    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    conditions[0]["description"] = unsafe_text

    with pytest.raises(ValueError, match="unsafe"):
        load_family_vault(write_vault(tmp_path, payload))


def test_existing_pgx_briefing_still_passes_unchanged() -> None:
    result = build_demo_briefing("sertraline")

    assert result.policy_passed is True
    assert result.findings_count == 1
    assert result.coverage["coverage_status"] == "matched_demo_rule"
