from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agent.live_chat import project_live_chat_evidence
from app.agent.models import AgentContext, ContextItem
from app.agent_trust.builders import BuildRefused
from app.agent_trust.canonical import canonical_bytes, sha256_hex

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)


def test_live_chat_projection_excludes_unprovenanced_items_and_binds_content_hash() -> None:
    context = AgentContext(
        source_kind="product_core",
        family_label="Active Person vault",
        items=[
            ContextItem(
                id="record-1",
                kind="medication",
                text="Recorded item",
                source_ids=["source-1"],
                provenance_status="source_backed",
            ),
            ContextItem(
                id="visit-1",
                kind="visit",
                text="No source visit",
                source_ids=[],
                provenance_status="recorded_without_source",
            ),
        ],
    )

    evidence, values = project_live_chat_evidence(context, "person-1", NOW)

    assert [item.evidence_id for item in evidence] == ["record-1"]
    assert evidence[0].selected_fields == ["medication.text"]
    assert values == (
        {
            "evidence_id": "record-1",
            "person_id": "person-1",
            "kind": "medication",
            "text": "Recorded item",
            "selected_fields": ("medication.text",),
            "source_ids": ("source-1",),
        },
    )
    assert evidence[0].content_sha256 == sha256_hex(canonical_bytes(dict(values[0])))


def test_live_chat_projection_fails_closed_when_context_exceeds_bound() -> None:
    context = AgentContext(
        source_kind="product_core",
        family_label="Active Person vault",
        items=[
            ContextItem(
                id=f"record-{index}",
                kind="lab",
                text="Recorded item",
                source_ids=[f"source-{index}"],
                provenance_status="source_backed",
            )
            for index in range(101)
        ],
    )

    with pytest.raises(BuildRefused, match="context_limit_exceeded"):
        project_live_chat_evidence(context, "person-1", NOW)
