import pytest

from app.demo_pipeline import build_demo_briefing
from app.health_vault.loader import load_demo_family_vault
from app.health_vault.read_model import build_vault_read_model


def test_read_model_builds_from_demo_family_vault() -> None:
    dataset = load_demo_family_vault()

    read_model = build_vault_read_model(dataset)

    assert read_model.dataset_id == "demo-family-vault-v1a"
    assert read_model.family.id == "family-demo-01"
    assert read_model.family.demo_only is True
    assert read_model.family.synthetic is True


def test_read_model_includes_all_synthetic_family_members() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    assert [person.id for person in read_model.people] == [
        "person-alex",
        "person-jordan",
        "person-sam",
    ]
    assert all(person.synthetic for person in read_model.people)


def test_relationship_summaries_are_present() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    assert len(read_model.relationships) == 2
    assert read_model.relationships[0].person_id == "person-alex"
    assert read_model.relationships[0].related_person_id == "person-jordan"
    assert read_model.relationships[0].relationship_type == "spouse"


def test_medications_are_grouped_by_person_as_recorded_context() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    alex_medications = read_model.medications_by_person["person-alex"]
    assert [medication.name for medication in alex_medications] == ["sertraline"]
    assert alex_medications[0].safety_label == "recorded_medication_context_not_recommendation"
    assert alex_medications[0].source_links


def test_conditions_are_grouped_by_person_as_recorded_context_not_diagnosis() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    alex_conditions = read_model.conditions_by_person["person-alex"]
    assert [condition.name for condition in alex_conditions] == [
        "Sleep concern recorded by demo user"
    ]
    assert alex_conditions[0].safety_label == "recorded_context_not_system_diagnosis"
    assert alex_conditions[0].source_links


def test_labs_are_grouped_by_person_without_interpretation() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    alex_labs = read_model.labs_by_person["person-alex"]
    assert [lab.name for lab in alex_labs] == ["A1c"]
    assert alex_labs[0].safety_label == "recorded_lab_context_not_interpretation"
    assert alex_labs[0].source_links


def test_visits_are_included_with_sources() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    alex_visits = read_model.visits_by_person["person-alex"]
    assert [visit.visit_type for visit in alex_visits] == ["primary care"]
    assert alex_visits[0].source_links


def test_timeline_is_sorted_by_date_and_source_linked() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    dates = [event.date for event in read_model.timeline.events]
    assert dates == sorted(dates)
    assert all(event.source_links for event in read_model.timeline.events)


def test_question_threads_are_included_as_questions_not_answers() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    assert len(read_model.questions) == 2
    assert {question.scope for question in read_model.questions} == {"person", "family"}
    assert all(
        question.safety_label == "recorded_question_not_answer"
        for question in read_model.questions
    )
    assert all(question.source_links for question in read_model.questions)


def test_provenance_coverage_is_complete_for_valid_demo_dataset() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())

    assert read_model.provenance_coverage.total_important_records == 14
    assert read_model.provenance_coverage.records_with_source == 14
    assert read_model.provenance_coverage.records_missing_source == 0
    assert read_model.provenance_coverage.missing_source_item_ids == []


def test_missing_provenance_causes_failure() -> None:
    dataset = load_demo_family_vault()
    lab_without_source = dataset.lab_results[0].model_copy(update={"evidence": []})
    invalid_dataset = dataset.model_copy(
        update={"lab_results": [lab_without_source, *dataset.lab_results[1:]]}
    )

    with pytest.raises(ValueError, match="provenance"):
        build_vault_read_model(invalid_dataset)


def test_non_demo_dataset_can_build_for_local_file_mode() -> None:
    dataset = load_demo_family_vault().model_copy(update={"demo_only": False})

    read_model = build_vault_read_model(dataset)

    assert read_model.family.demo_only is False
    notices = {notice.code: notice.message for notice in read_model.safety_notices}
    assert notices["local_operator_supplied_data"] == (
        "This dataset comes from an operator-supplied local vault file."
    )


def test_non_synthetic_dataset_can_build_for_local_file_mode() -> None:
    dataset = load_demo_family_vault().model_copy(update={"synthetic": False})

    read_model = build_vault_read_model(dataset)

    assert read_model.family.synthetic is False


def test_unsafe_text_in_surfaced_fields_fails() -> None:
    dataset = load_demo_family_vault()
    unsafe_condition = dataset.conditions[0].model_copy(
        update={"description": "OpenCare diagnosis: insomnia."}
    )
    invalid_dataset = dataset.model_copy(
        update={"conditions": [unsafe_condition, *dataset.conditions[1:]]}
    )

    with pytest.raises(ValueError, match="unsafe"):
        build_vault_read_model(invalid_dataset)


def test_read_model_includes_safety_boundary_notices() -> None:
    read_model = build_vault_read_model(load_demo_family_vault())
    notices = {notice.code: notice.message for notice in read_model.safety_notices}

    assert notices["no_diagnosis"] == "OpenCare does not diagnose."
    assert notices["no_treatment_recommendation"] == "OpenCare does not recommend treatment."
    assert notices["no_dosage_guidance"] == "OpenCare does not provide dosage guidance."
    assert notices["no_start_stop_medication"] == (
        "OpenCare does not tell users to start or stop medication."
    )
    assert notices["synthetic_demo_only"] == "This dataset is synthetic/demo-only."
    assert notices["deterministic_reorganization"] == (
        "Summaries are deterministic reorganizations of recorded vault data."
    )


def test_existing_pgx_briefing_still_passes_unchanged() -> None:
    result = build_demo_briefing("sertraline")

    assert result.policy_passed is True
    assert result.findings_count == 1
    assert result.coverage["coverage_status"] == "matched_demo_rule"
