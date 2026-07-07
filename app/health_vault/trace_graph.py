from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from app.health_vault.artifacts import (
    MANIFEST_FILENAME,
    READ_MODEL_FILENAME,
    SUMMARY_FILENAME,
)
from app.health_vault.models import UNSAFE_TEXT_PATTERNS, VaultDataset
from app.health_vault.read_model import (
    ConditionOverview,
    LabOverview,
    MedicationOverview,
    ProvenanceOverview,
    QuestionOverview,
    TimelineEventOverview,
    VaultReadModel,
    VisitOverview,
    build_vault_read_model,
)

TraceNodeType = Literal[
    "family",
    "person",
    "relationship",
    "recorded_medication",
    "recorded_condition",
    "recorded_lab",
    "visit",
    "timeline_event",
    "question_thread",
    "document_source",
    "safety_boundary",
    "artifact",
]
TraceEdgeType = Literal[
    "belongs_to_person",
    "linked_to_source",
    "recorded_in_timeline",
    "part_of_family",
    "has_relationship",
    "covered_by_safety_boundary",
    "emitted_in_artifact",
]
TraceableOverview = (
    MedicationOverview
    | ConditionOverview
    | LabOverview
    | VisitOverview
    | TimelineEventOverview
    | QuestionOverview
)


class TraceNode(BaseModel):
    id: str = Field(min_length=1)
    node_type: TraceNodeType
    label: str = Field(min_length=1)
    safety_label: str | None = None


class TraceEdge(BaseModel):
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    edge_type: TraceEdgeType


class TraceGraphRecordRow(BaseModel):
    record_label: str = Field(min_length=1)
    person_label: str = Field(min_length=1)
    source_label: str = Field(min_length=1)
    safety_label: str = Field(min_length=1)
    node_type: TraceNodeType


class TraceGraphSummary(BaseModel):
    node_count: int
    edge_count: int
    source_linked_record_count: int
    missing_source_record_count: int
    safety_boundary_count: int
    demo_only: bool
    synthetic: bool
    no_llm_generation: bool
    no_genetics: bool
    no_medical_advice: bool


class TraceGraph(BaseModel):
    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdge] = Field(default_factory=list)
    record_rows: list[TraceGraphRecordRow] = Field(default_factory=list)
    summary: TraceGraphSummary


def build_vault_trace_graph(dataset_or_read_model: VaultDataset | VaultReadModel) -> TraceGraph:
    read_model = _coerce_read_model(dataset_or_read_model)
    _assert_trace_graph_inputs(read_model)

    nodes: list[TraceNode] = []
    edges: list[TraceEdge] = []
    record_rows: list[TraceGraphRecordRow] = []

    artifact_node_ids = {
        READ_MODEL_FILENAME: _artifact_node_id(READ_MODEL_FILENAME),
        SUMMARY_FILENAME: _artifact_node_id(SUMMARY_FILENAME),
        MANIFEST_FILENAME: _artifact_node_id(MANIFEST_FILENAME),
    }
    people_lookup = {person.id: person.display_name for person in read_model.people}
    safety_node_ids = {
        notice.code: _safety_node_id(notice.code) for notice in read_model.safety_notices
    }
    timeline_node_ids = {
        event.id: _record_node_id("timeline_event", event.id)
        for event in read_model.timeline.events
    }

    family_node_id = _family_node_id(read_model.family.id)
    nodes.append(
        TraceNode(
            id=family_node_id,
            node_type="family",
            label=read_model.family.display_name,
        )
    )

    for filename, node_id in artifact_node_ids.items():
        nodes.append(TraceNode(id=node_id, node_type="artifact", label=filename))

    for person in read_model.people:
        node_id = _person_node_id(person.id)
        nodes.append(TraceNode(id=node_id, node_type="person", label=person.display_name))
        edges.append(
            TraceEdge(
                from_node_id=node_id,
                to_node_id=family_node_id,
                edge_type="part_of_family",
            )
        )

    for relationship in read_model.relationships:
        node_id = _relationship_node_id(relationship.id)
        person_name = people_lookup.get(relationship.person_id, relationship.person_id)
        related_name = people_lookup.get(
            relationship.related_person_id,
            relationship.related_person_id,
        )
        nodes.append(
            TraceNode(
                id=node_id,
                node_type="relationship",
                label=f"{person_name} -> {related_name} ({relationship.relationship_type})",
            )
        )
        edges.extend(
            [
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=_person_node_id(relationship.person_id),
                    edge_type="has_relationship",
                ),
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=_person_node_id(relationship.related_person_id),
                    edge_type="has_relationship",
                ),
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=family_node_id,
                    edge_type="part_of_family",
                ),
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=artifact_node_ids[READ_MODEL_FILENAME],
                    edge_type="emitted_in_artifact",
                ),
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=artifact_node_ids[SUMMARY_FILENAME],
                    edge_type="emitted_in_artifact",
                ),
            ]
        )

    source_node_ids: dict[str, str] = {}
    for source_link in _all_source_links(read_model):
        if source_link.source_id in source_node_ids:
            continue
        node_id = _source_node_id(source_link.source_id)
        source_node_ids[source_link.source_id] = node_id
        nodes.append(
            TraceNode(
                id=node_id,
                node_type="document_source",
                label=source_link.source_title,
            )
        )
        edges.append(
            TraceEdge(
                from_node_id=node_id,
                to_node_id=artifact_node_ids[READ_MODEL_FILENAME],
                edge_type="emitted_in_artifact",
            )
        )

    for notice in read_model.safety_notices:
        node_id = safety_node_ids[notice.code]
        nodes.append(
            TraceNode(
                id=node_id,
                node_type="safety_boundary",
                label=notice.message,
            )
        )
        edges.extend(
            [
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=artifact_node_ids[READ_MODEL_FILENAME],
                    edge_type="emitted_in_artifact",
                ),
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=artifact_node_ids[MANIFEST_FILENAME],
                    edge_type="emitted_in_artifact",
                ),
            ]
        )

    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="recorded_medication",
            items=[
                item
                for items in read_model.medications_by_person.values()
                for item in items
            ],
        )
    )
    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="recorded_condition",
            items=[
                item
                for items in read_model.conditions_by_person.values()
                for item in items
            ],
        )
    )
    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="recorded_lab",
            items=[item for items in read_model.labs_by_person.values() for item in items],
        )
    )
    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="visit",
            items=[item for items in read_model.visits_by_person.values() for item in items],
        )
    )
    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="timeline_event",
            items=read_model.timeline.events,
        )
    )
    record_rows.extend(
        _append_trace_records(
            nodes=nodes,
            edges=edges,
            artifact_node_ids=artifact_node_ids,
            family_node_id=family_node_id,
            people_lookup=people_lookup,
            safety_node_ids=safety_node_ids,
            timeline_node_ids=timeline_node_ids,
            record_type="question_thread",
            items=read_model.questions,
        )
    )

    summary = TraceGraphSummary(
        node_count=len(nodes),
        edge_count=len(edges),
        source_linked_record_count=len(record_rows),
        missing_source_record_count=0,
        safety_boundary_count=len(read_model.safety_notices),
        demo_only=read_model.family.demo_only,
        synthetic=read_model.family.synthetic,
        no_llm_generation=True,
        no_genetics=True,
        no_medical_advice=True,
    )
    graph = TraceGraph(nodes=nodes, edges=edges, record_rows=record_rows, summary=summary)
    _assert_safe_text(graph.model_dump())
    return graph


def _coerce_read_model(dataset_or_read_model: VaultDataset | VaultReadModel) -> VaultReadModel:
    if isinstance(dataset_or_read_model, VaultReadModel):
        return dataset_or_read_model
    return build_vault_read_model(dataset_or_read_model)


def _assert_trace_graph_inputs(read_model: VaultReadModel) -> None:
    if not read_model.family.demo_only:
        raise ValueError("Trace graph requires demo_only data.")
    if not read_model.family.synthetic:
        raise ValueError("Trace graph requires synthetic data.")
    if read_model.provenance_coverage.records_missing_source != 0:
        raise ValueError("Trace graph requires complete provenance coverage.")
    if read_model.provenance_coverage.missing_source_item_ids:
        raise ValueError("Trace graph requires complete provenance coverage.")
    _assert_safe_text(read_model.model_dump())


def _append_trace_records(
    *,
    nodes: list[TraceNode],
    edges: list[TraceEdge],
    artifact_node_ids: dict[str, str],
    family_node_id: str,
    people_lookup: dict[str, str],
    safety_node_ids: dict[str, str],
    timeline_node_ids: dict[str, str],
    record_type: TraceNodeType,
    items: Sequence[TraceableOverview],
) -> list[TraceGraphRecordRow]:
    rows: list[TraceGraphRecordRow] = []
    for item in items:
        if not item.source_links:
            raise ValueError(f"Trace graph record {item.id} is missing provenance.")

        node_id = _record_node_id(record_type, item.id)
        label = _record_label(record_type, item)
        person_label = _person_label(item, people_lookup)
        source_label = ", ".join(source.source_title for source in item.source_links)

        nodes.append(
            TraceNode(
                id=node_id,
                node_type=record_type,
                label=label,
                safety_label=item.safety_label,
            )
        )

        if item.person_id is not None:
            edges.append(
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=_person_node_id(item.person_id),
                    edge_type="belongs_to_person",
                )
            )
        else:
            edges.append(
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=family_node_id,
                    edge_type="part_of_family",
                )
            )

        for source in item.source_links:
            edges.append(
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=_source_node_id(source.source_id),
                    edge_type="linked_to_source",
                )
            )

        for safety_node_id in safety_node_ids.values():
            edges.append(
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=safety_node_id,
                    edge_type="covered_by_safety_boundary",
                )
            )

        for artifact_node_id in artifact_node_ids.values():
            edges.append(
                TraceEdge(
                    from_node_id=node_id,
                    to_node_id=artifact_node_id,
                    edge_type="emitted_in_artifact",
                )
            )

        if record_type != "timeline_event":
            timeline_node_id = _find_timeline_edge_target(item, timeline_node_ids)
            if timeline_node_id is not None:
                edges.append(
                    TraceEdge(
                        from_node_id=node_id,
                        to_node_id=timeline_node_id,
                        edge_type="recorded_in_timeline",
                    )
                )

        rows.append(
            TraceGraphRecordRow(
                record_label=label,
                person_label=person_label,
                source_label=source_label,
                safety_label=item.safety_label,
                node_type=record_type,
            )
        )
    return rows


def _record_label(record_type: TraceNodeType, item: TraceableOverview) -> str:
    if isinstance(item, MedicationOverview):
        return f"{item.name} ({item.status})"
    if isinstance(item, ConditionOverview):
        return f"{item.name} ({item.status})"
    if isinstance(item, LabOverview):
        return f"{item.name} ({item.collected_on})"
    if isinstance(item, VisitOverview):
        return f"{item.visit_type} ({item.date})"
    if isinstance(item, TimelineEventOverview):
        return f"{item.title} ({item.date})"
    return item.question


def _person_label(item: TraceableOverview, people_lookup: dict[str, str]) -> str:
    if item.person_id is None:
        return "Family"
    return people_lookup.get(item.person_id, item.person_id)


def _find_timeline_edge_target(
    item: TraceableOverview,
    timeline_node_ids: dict[str, str],
) -> str | None:
    if isinstance(item, LabOverview) and item.id.startswith("lab-"):
        event_id = item.id.replace("lab-", "event-", 1)
        return timeline_node_ids.get(event_id)
    if isinstance(item, VisitOverview) and item.id.startswith("visit-"):
        suffix = item.id.removeprefix("visit-")
        return timeline_node_ids.get(f"event-{suffix}")
    return None


def _all_source_links(read_model: VaultReadModel) -> list[ProvenanceOverview]:
    return [
        *[
            source
            for items in read_model.medications_by_person.values()
            for item in items
            for source in item.source_links
        ],
        *[
            source
            for items in read_model.conditions_by_person.values()
            for item in items
            for source in item.source_links
        ],
        *[
            source
            for items in read_model.labs_by_person.values()
            for item in items
            for source in item.source_links
        ],
        *[
            source
            for items in read_model.visits_by_person.values()
            for item in items
            for source in item.source_links
        ],
        *[source for item in read_model.timeline.events for source in item.source_links],
        *[source for item in read_model.questions for source in item.source_links],
    ]


def _family_node_id(family_id: str) -> str:
    return f"family:{family_id}"


def _person_node_id(person_id: str) -> str:
    return f"person:{person_id}"


def _relationship_node_id(relationship_id: str) -> str:
    return f"relationship:{relationship_id}"


def _record_node_id(record_type: TraceNodeType, record_id: str) -> str:
    return f"{record_type}:{record_id}"


def _source_node_id(source_id: str) -> str:
    return f"source:{source_id}"


def _safety_node_id(code: str) -> str:
    return f"safety:{code}"


def _artifact_node_id(filename: str) -> str:
    return f"artifact:{filename}"


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
