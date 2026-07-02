from pydantic import BaseModel, Field

from app.health_vault.models import (
    UNSAFE_TEXT_PATTERNS,
    Condition,
    DocumentSource,
    EvidenceLink,
    LabResult,
    Medication,
    QuestionThread,
    Relationship,
    TimelineEvent,
    VaultDataset,
    Visit,
)


class ProvenanceOverview(BaseModel):
    source_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    strength: str = Field(min_length=1)
    note: str = Field(min_length=1)


class SourceCoverage(BaseModel):
    total_important_records: int
    records_with_source: int
    records_missing_source: int
    missing_source_item_ids: list[str] = Field(default_factory=list)


class SafetyBoundaryNotice(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class FamilyOverview(BaseModel):
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    demo_only: bool
    synthetic: bool
    people_count: int
    relationship_count: int


class PersonOverview(BaseModel):
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    synthetic: bool


class RelationshipOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    related_person_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)


class MedicationOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reason_context: str
    safety_label: str = "recorded_medication_context_not_recommendation"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


class ConditionOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    description: str
    safety_label: str = "recorded_context_not_system_diagnosis"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


class LabOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    result_text: str = Field(min_length=1)
    collected_on: str = Field(min_length=1)
    safety_label: str = "recorded_lab_context_not_interpretation"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


class VisitOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    visit_type: str = Field(min_length=1)
    date: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    safety_label: str = "recorded_visit_context_not_medical_advice"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


class TimelineEventOverview(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    date: str = Field(min_length=1)
    title: str = Field(min_length=1)
    safety_label: str = "recorded_timeline_event"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


class TimelineOverview(BaseModel):
    events: list[TimelineEventOverview] = Field(default_factory=list)


class QuestionOverview(BaseModel):
    id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    person_id: str | None = None
    status: str = Field(min_length=1)
    question: str = Field(min_length=1)
    safety_label: str = "recorded_question_not_answer"
    source_links: list[ProvenanceOverview] = Field(default_factory=list)


type SummaryItem = (
    MedicationOverview
    | ConditionOverview
    | LabOverview
    | VisitOverview
    | TimelineEventOverview
    | QuestionOverview
)


class VaultReadModel(BaseModel):
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    family: FamilyOverview
    people: list[PersonOverview] = Field(default_factory=list)
    relationships: list[RelationshipOverview] = Field(default_factory=list)
    medications_by_person: dict[str, list[MedicationOverview]] = Field(default_factory=dict)
    conditions_by_person: dict[str, list[ConditionOverview]] = Field(default_factory=dict)
    labs_by_person: dict[str, list[LabOverview]] = Field(default_factory=dict)
    visits_by_person: dict[str, list[VisitOverview]] = Field(default_factory=dict)
    timeline: TimelineOverview
    questions: list[QuestionOverview] = Field(default_factory=list)
    provenance_coverage: SourceCoverage
    safety_notices: list[SafetyBoundaryNotice] = Field(default_factory=list)


def build_vault_read_model(dataset: VaultDataset) -> VaultReadModel:
    _validate_dataset_boundary(dataset)
    _assert_safe_text(dataset.model_dump())

    source_lookup = {source.id: source for source in dataset.document_sources}
    people_ids = [person.id for person in dataset.people]

    read_model = VaultReadModel(
        dataset_id=dataset.dataset_id,
        version=dataset.version,
        family=FamilyOverview(
            id=dataset.family.id,
            display_name=dataset.family.display_name,
            demo_only=dataset.demo_only,
            synthetic=dataset.synthetic and dataset.family.synthetic,
            people_count=len(dataset.people),
            relationship_count=len(dataset.relationships),
        ),
        people=[
            PersonOverview(
                id=person.id,
                display_name=person.display_name,
                role=person.role,
                synthetic=person.synthetic,
            )
            for person in dataset.people
        ],
        relationships=[
            _relationship_overview(relationship)
            for relationship in dataset.relationships
        ],
        medications_by_person=_medications_by_person(dataset, source_lookup, people_ids),
        conditions_by_person=_conditions_by_person(dataset, source_lookup, people_ids),
        labs_by_person=_labs_by_person(dataset, source_lookup, people_ids),
        visits_by_person=_visits_by_person(dataset, source_lookup, people_ids),
        timeline=TimelineOverview(
            events=sorted(
                [
                    _timeline_event_overview(event, source_lookup)
                    for event in dataset.timeline_events
                ],
                key=lambda event: (event.date, event.id),
            )
        ),
        questions=[
            _question_overview(question, source_lookup)
            for question in sorted(dataset.question_threads, key=lambda item: item.id)
        ],
        provenance_coverage=_source_coverage(dataset),
        safety_notices=_safety_notices(),
    )
    _assert_all_summary_items_have_sources(read_model)
    _assert_safe_text(read_model.model_dump())
    return read_model


def _validate_dataset_boundary(dataset: VaultDataset) -> None:
    if not dataset.demo_only:
        raise ValueError("Read model requires demo_only datasets.")
    if not dataset.synthetic:
        raise ValueError("Read model requires synthetic datasets.")
    if not dataset.family.synthetic:
        raise ValueError("Read model requires a synthetic family.")
    for person in dataset.people:
        if not person.synthetic:
            raise ValueError(f"Read model requires synthetic people: {person.id}")
    for source in dataset.document_sources:
        if not source.demo_only:
            raise ValueError(f"Read model requires demo_only sources: {source.id}")
        if not source.synthetic:
            raise ValueError(f"Read model requires synthetic sources: {source.id}")


def _relationship_overview(relationship: Relationship) -> RelationshipOverview:
    return RelationshipOverview(
        id=relationship.id,
        person_id=relationship.person_id,
        related_person_id=relationship.related_person_id,
        relationship_type=relationship.relationship_type,
    )


def _medications_by_person(
    dataset: VaultDataset,
    source_lookup: dict[str, DocumentSource],
    people_ids: list[str],
) -> dict[str, list[MedicationOverview]]:
    grouped: dict[str, list[MedicationOverview]] = {person_id: [] for person_id in people_ids}
    for medication in sorted(dataset.medications, key=lambda item: item.id):
        grouped[medication.person_id].append(_medication_overview(medication, source_lookup))
    return grouped


def _medication_overview(
    medication: Medication,
    source_lookup: dict[str, DocumentSource],
) -> MedicationOverview:
    return MedicationOverview(
        id=medication.id,
        person_id=medication.person_id,
        name=medication.name,
        status=medication.status,
        reason_context=medication.reason_context,
        source_links=_source_links(medication.id, medication.evidence, source_lookup),
    )


def _conditions_by_person(
    dataset: VaultDataset,
    source_lookup: dict[str, DocumentSource],
    people_ids: list[str],
) -> dict[str, list[ConditionOverview]]:
    grouped: dict[str, list[ConditionOverview]] = {person_id: [] for person_id in people_ids}
    for condition in sorted(dataset.conditions, key=lambda item: item.id):
        grouped[condition.person_id].append(_condition_overview(condition, source_lookup))
    return grouped


def _condition_overview(
    condition: Condition,
    source_lookup: dict[str, DocumentSource],
) -> ConditionOverview:
    return ConditionOverview(
        id=condition.id,
        person_id=condition.person_id,
        name=condition.name,
        status=condition.status,
        description=condition.description,
        source_links=_source_links(condition.id, condition.evidence, source_lookup),
    )


def _labs_by_person(
    dataset: VaultDataset,
    source_lookup: dict[str, DocumentSource],
    people_ids: list[str],
) -> dict[str, list[LabOverview]]:
    grouped: dict[str, list[LabOverview]] = {person_id: [] for person_id in people_ids}
    for lab_result in sorted(dataset.lab_results, key=lambda item: (item.collected_on, item.id)):
        grouped[lab_result.person_id].append(_lab_overview(lab_result, source_lookup))
    return grouped


def _lab_overview(
    lab_result: LabResult,
    source_lookup: dict[str, DocumentSource],
) -> LabOverview:
    return LabOverview(
        id=lab_result.id,
        person_id=lab_result.person_id,
        name=lab_result.name,
        result_text=lab_result.result_text,
        collected_on=lab_result.collected_on,
        source_links=_source_links(lab_result.id, lab_result.evidence, source_lookup),
    )


def _visits_by_person(
    dataset: VaultDataset,
    source_lookup: dict[str, DocumentSource],
    people_ids: list[str],
) -> dict[str, list[VisitOverview]]:
    grouped: dict[str, list[VisitOverview]] = {person_id: [] for person_id in people_ids}
    for visit in sorted(dataset.visits, key=lambda item: (item.date, item.id)):
        grouped[visit.person_id].append(_visit_overview(visit, source_lookup))
    return grouped


def _visit_overview(
    visit: Visit,
    source_lookup: dict[str, DocumentSource],
) -> VisitOverview:
    return VisitOverview(
        id=visit.id,
        person_id=visit.person_id,
        visit_type=visit.visit_type,
        date=visit.date,
        summary=visit.summary,
        source_links=_source_links(visit.id, visit.evidence, source_lookup),
    )


def _timeline_event_overview(
    event: TimelineEvent,
    source_lookup: dict[str, DocumentSource],
) -> TimelineEventOverview:
    return TimelineEventOverview(
        id=event.id,
        person_id=event.person_id,
        event_type=event.event_type,
        date=event.date,
        title=event.title,
        source_links=_source_links(event.id, event.evidence, source_lookup),
    )


def _question_overview(
    question: QuestionThread,
    source_lookup: dict[str, DocumentSource],
) -> QuestionOverview:
    return QuestionOverview(
        id=question.id,
        scope=question.scope,
        person_id=question.person_id,
        status=question.status,
        question=question.question,
        source_links=_source_links(question.id, question.evidence, source_lookup),
    )


def _source_links(
    item_id: str,
    evidence: list[EvidenceLink],
    source_lookup: dict[str, DocumentSource],
) -> list[ProvenanceOverview]:
    if not evidence:
        raise ValueError(f"Summary item {item_id} is missing provenance.")

    links: list[ProvenanceOverview] = []
    for link in evidence:
        source = source_lookup.get(link.source_id)
        if source is None:
            raise ValueError(f"Summary item {item_id} references unknown source: {link.source_id}")
        links.append(
            ProvenanceOverview(
                source_id=source.id,
                source_title=source.title,
                source_type=source.source_type,
                strength=link.strength,
                note=link.note,
            )
        )
    return links


def _source_coverage(dataset: VaultDataset) -> SourceCoverage:
    important_records = [
        *[(condition.id, condition.evidence) for condition in dataset.conditions],
        *[(medication.id, medication.evidence) for medication in dataset.medications],
        *[(lab_result.id, lab_result.evidence) for lab_result in dataset.lab_results],
        *[(visit.id, visit.evidence) for visit in dataset.visits],
        *[(event.id, event.evidence) for event in dataset.timeline_events],
        *[(question.id, question.evidence) for question in dataset.question_threads],
    ]
    missing_source_item_ids = [
        record_id for record_id, evidence in important_records if not evidence
    ]
    return SourceCoverage(
        total_important_records=len(important_records),
        records_with_source=len(important_records) - len(missing_source_item_ids),
        records_missing_source=len(missing_source_item_ids),
        missing_source_item_ids=missing_source_item_ids,
    )


def _safety_notices() -> list[SafetyBoundaryNotice]:
    return [
        SafetyBoundaryNotice(code="no_diagnosis", message="OpenCare does not diagnose."),
        SafetyBoundaryNotice(
            code="no_treatment_recommendation",
            message="OpenCare does not recommend treatment.",
        ),
        SafetyBoundaryNotice(
            code="no_dosage_guidance",
            message="OpenCare does not provide dosage guidance.",
        ),
        SafetyBoundaryNotice(
            code="no_start_stop_medication",
            message="OpenCare does not tell users to start or stop medication.",
        ),
        SafetyBoundaryNotice(
            code="synthetic_demo_only",
            message="This dataset is synthetic/demo-only.",
        ),
        SafetyBoundaryNotice(
            code="deterministic_reorganization",
            message="Summaries are deterministic reorganizations of recorded demo data.",
        ),
    ]


def _assert_all_summary_items_have_sources(read_model: VaultReadModel) -> None:
    grouped_items: list[SummaryItem] = [
        *[item for items in read_model.medications_by_person.values() for item in items],
        *[item for items in read_model.conditions_by_person.values() for item in items],
        *[item for items in read_model.labs_by_person.values() for item in items],
        *[item for items in read_model.visits_by_person.values() for item in items],
        *read_model.timeline.events,
        *read_model.questions,
    ]
    for item in grouped_items:
        if not item.source_links:
            raise ValueError(f"Summary item {item.id} is missing provenance.")


def _assert_safe_text(value: object) -> None:
    for text in _walk_strings(value):
        normalized = text.lower()
        for reason, patterns in UNSAFE_TEXT_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    raise ValueError(f"unsafe text detected ({reason}): {pattern}")


def _walk_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(_walk_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings = []
        for nested_value in value:
            strings.extend(_walk_strings(nested_value))
        return strings
    return []
