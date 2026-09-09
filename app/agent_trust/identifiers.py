from __future__ import annotations

from typing import Final, Literal

PurposeId = Literal[
    "visit_preparation",
    "record_explanation",
    "clinician_briefing",
    "document_fact_extraction",
]
ActionId = Literal[
    "answer_question",
    "draft_visit_brief",
    "summarize_records",
    "document.extract_facts",
]
ToolId = Literal["context.read", "source.read", "brief.draft"]

PURPOSE_IDS: Final[frozenset[str]] = frozenset(
    {
        "visit_preparation",
        "record_explanation",
        "clinician_briefing",
        "document_fact_extraction",
    }
)
ACTION_REQUIREMENTS: Final[dict[str, tuple[frozenset[str], frozenset[str]]]] = {
    "answer_question": (
        frozenset({"person.read", "source.read", "chat.use"}),
        frozenset({"context.read", "source.read"}),
    ),
    "draft_visit_brief": (
        frozenset({"person.read", "source.read", "brief.read"}),
        frozenset({"context.read", "source.read", "brief.draft"}),
    ),
    "summarize_records": (
        frozenset({"person.read", "source.read"}),
        frozenset({"context.read", "source.read"}),
    ),
    "document.extract_facts": (
        frozenset({"document.read"}),
        frozenset({"source.read"}),
    ),
}
TOOL_IDS: Final[frozenset[str]] = frozenset({"context.read", "source.read", "brief.draft"})
PROHIBITED_OPERATIONS: Final[tuple[str, ...]] = (
    "canonical_record_mutation",
    "diagnosis",
    "dosage_guidance",
    "medication_start_stop_instruction",
    "medication_selection",
    "treatment_planning",
)
DEFAULT_DISCLOSURE_CONSTRAINTS: Final[tuple[str, ...]] = (
    "disclose_only_selected_fields",
    "do_not_retain_beyond_declared_retention",
)
