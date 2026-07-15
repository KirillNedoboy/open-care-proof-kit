from typing import Any

from app.agent.models import AgentContext, ContextItem, ContextSource
from app.health_vault.runtime_loader import ActiveVault


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
