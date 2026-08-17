from typing import Any

from app.agent.models import AgentContext, ContextItem, ContextSource
from app.health_vault.runtime_loader import ActiveVault
from app.product_core.errors import PersonNotFoundError
from app.product_core.models import (
    ConditionCandidateDetail,
    LabCandidateDetail,
    isoformat_utc,
)
from app.product_core.runtime import ProductCoreRuntime


def build_agent_context(active_vault: ActiveVault) -> AgentContext:
    read_model = active_vault.read_model
    sources = [
        ContextSource(source_id=source.id, title=source.title, source_type=source.source_type)
        for source in active_vault.dataset.document_sources
    ]
    items: list[ContextItem] = []
    for person in read_model.people:
        items.append(
            ContextItem(
                id=person.id,
                kind="person",
                text=f"{person.display_name} ({person.role})",
                provenance_status="recorded_without_source",
            )
        )
    for grouped_items, kind, fields in (
        (read_model.medications_by_person, "medication", ("name", "status", "reason_context")),
        (read_model.conditions_by_person, "condition", ("name", "status", "description")),
        (read_model.labs_by_person, "lab", ("name", "result_text", "collected_on")),
        (read_model.visits_by_person, "visit", ("visit_type", "date", "summary")),
    ):
        for records in grouped_items.values():
            for record in records:
                items.append(_record_item(record, kind, fields))
    for event in read_model.timeline.events:
        items.append(_record_item(event, "timeline", ("date", "title", "event_type")))
    for question in read_model.questions:
        items.append(_record_item(question, "recorded_question", ("question", "status", "scope")))
    return AgentContext(
        source_kind=active_vault.source_kind,
        family_label=read_model.family.display_name,
        people=[person.display_name for person in read_model.people],
        items=items,
        sources=sources,
    )


def build_product_core_agent_context(
    runtime: ProductCoreRuntime, person_id: str
) -> AgentContext:
    """Build one Person's deterministic chat context without reading source payloads."""
    with runtime.database.uow() as uow:
        person = uow.people.get(person_id)
        if person is None or not person.is_active:
            raise PersonNotFoundError("Person was not found.")
        sources = sorted(
            uow.sources.list_for_person(person_id),
            key=lambda source: (isoformat_utc(source.created_at), source.id),
        )
        medications = sorted(
            uow.canonical_records.list_for_person(
                person_id, include_inactive=False, fact_type="medication"
            ),
            key=lambda record: (isoformat_utc(record.confirmed_at), record.id),
        )
        conditions = sorted(
            uow.canonical_records.list_for_person(
                person_id, include_inactive=False, fact_type="condition"
            ),
            key=lambda record: (isoformat_utc(record.confirmed_at), record.id),
        )
        labs = sorted(
            uow.canonical_records.list_for_person(
                person_id, include_inactive=False, fact_type="lab"
            ),
            key=lambda record: (isoformat_utc(record.confirmed_at), record.id),
        )
        timeline = sorted(
            uow.timeline_events.list_for_person(person_id),
            key=lambda event: (isoformat_utc(event.event_at), event.id),
        )
        visits = sorted(
            uow.visits.list_for_person(person_id),
            key=lambda visit: (isoformat_utc(visit.created_at), visit.visit_id),
        )
        questions = [
            question
            for visit in visits
            for question in sorted(
                uow.visit_questions.list_for_visit(visit.visit_id),
                key=lambda item: (item.position, item.question_id),
            )
        ]
    items = [
        ContextItem(
            id=person.person_id,
            kind="person",
            text=person.display_name,
            provenance_status="recorded_without_source",
        )
    ]
    items.extend(
        ContextItem(
            id=record.id,
            kind="medication",
            text=" | ".join(
                value
                for value in (record.display_name, record.schedule_text, record.note)
                if value
            ),
            source_ids=[record.source_id],
            provenance_status="source_backed",
        )
        for record in medications
    )
    for record in conditions:
        detail = record.detail
        assert isinstance(detail, ConditionCandidateDetail)
        items.append(
            ContextItem(
                id=record.id,
                kind="condition",
                text=" | ".join(
                    value
                    for value in (record.display_name, detail.status_text)
                    if value
                ),
                source_ids=[record.source_id],
                provenance_status="source_backed",
            )
        )
    for record in labs:
        detail = record.detail
        assert isinstance(detail, LabCandidateDetail)
        items.append(
            ContextItem(
                id=record.id,
                kind="lab",
                text=" | ".join(
                    value
                    for value in (
                        detail.test_name,
                        detail.result_text,
                        detail.unit_text,
                        (
                            f"flag {detail.source_flag_text} (as reported)"
                            if detail.source_flag_text
                            else None
                        ),
                    )
                    if value
                ),
                source_ids=[record.source_id],
                provenance_status="source_backed",
            )
        )
    items.extend(
        ContextItem(
            id=event.id,
            kind="timeline",
            text=" | ".join(
                (isoformat_utc(event.event_at), event.title, event.event_type)
            ),
            source_ids=[event.source_id],
            provenance_status="source_backed",
        )
        for event in timeline
    )
    items.extend(
        ContextItem(
            id=visit.visit_id,
            kind="visit",
            text=" | ".join(
                value
                for value in (
                    visit.title,
                    visit.specialist,
                    None if visit.scheduled_date is None else visit.scheduled_date.isoformat(),
                )
                if value
            ),
            provenance_status="recorded_without_source",
        )
        for visit in visits
    )
    items.extend(
        ContextItem(
            id=question.question_id,
            kind="recorded_question",
            text=question.question_text,
            provenance_status="recorded_without_source",
        )
        for question in questions
    )
    return AgentContext(
        source_kind="product_core",
        family_label="Active Person vault",
        people=[person.display_name],
        items=items,
        sources=[
            ContextSource(
                source_id=source.id,
                title=f"Recorded {source.source_type.replace('_', ' ')} source",
                source_type=source.source_type,
            )
            for source in sources
        ],
    )


def _record_item(record: Any, kind: str, fields: tuple[str, ...]) -> ContextItem:
    values = [str(getattr(record, field)) for field in fields]
    source_ids = [link.source_id for link in record.source_links]
    return ContextItem(
        id=record.id,
        kind=kind,
        text=" | ".join(values),
        source_ids=source_ids,
        provenance_status="source_backed" if source_ids else "recorded_without_source",
    )
