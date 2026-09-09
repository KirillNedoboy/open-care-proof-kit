from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agent.live_chat import current_live_chat_evidence, project_live_chat_evidence
from app.agent.models import AgentContext, ContextItem
from app.agent_trust.builders import BuildRefused
from app.agent_trust.canonical import canonical_bytes, sha256_hex
from app.config import clear_settings_cache, load_settings
from app.product_core.models import Person
from app.product_core.runtime import create_product_core_runtime

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


NEW_RECORD_KINDS = frozenset({"procedure", "recommendation", "follow_up"})
NEW_RECORD_READ_SCOPES = frozenset(
    {"procedure.read", "recommendation.read", "follow_up.read"}
)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def product_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "product" / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    runtime = create_product_core_runtime(load_settings(None), clock=clock)
    runtime.database.migrate()
    with runtime.database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Profile person-1",
                created_at=clock(),
                updated_at=clock(),
                is_active=True,
            )
        )
    yield runtime
    clear_settings_cache()


def _confirm_new_record(runtime: object, person_id: str, fact_type: str) -> str:
    from app.product_core.models import (
        FollowUpCandidateInput,
        ProcedureCandidateInput,
        RecommendationCandidateInput,
    )

    source = runtime.sources.register_manual_entry(person_id, f"{fact_type} source")
    if fact_type == "procedure":
        detail = ProcedureCandidateInput(
            display_name="Colonoscopy",
            status_text="completed",
            date_text="March 2026",
        )
    elif fact_type == "recommendation":
        detail = RecommendationCandidateInput(
            instruction_text="Reduce sodium intake",
            context_text="cardiology visit",
        )
    else:
        detail = FollowUpCandidateInput(
            action_text="Repeat blood panel",
            timing_text="in 3 months",
            destination_text="Lab 12",
        )
    candidate = runtime.lifecycle.create_fact_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type=fact_type,
        detail_input=detail,
    )
    return runtime.lifecycle.confirm(candidate.id).id


def test_live_chat_projection_excludes_confirmed_new_records_without_read_scopes(
    product_runtime: object,
) -> None:
    source = product_runtime.sources.register_manual_entry("person-1", "Aspirin")
    candidate = product_runtime.lifecycle.create_candidate(
        person_id="person-1", source_id=source.id, display_name="Aspirin"
    )
    medication_id = product_runtime.lifecycle.confirm(candidate.id).id
    for fact_type in ("procedure", "recommendation", "follow_up"):
        _confirm_new_record(product_runtime, "person-1", fact_type)

    evidence, values = current_live_chat_evidence(product_runtime, "person-1", NOW)

    assert [value["evidence_id"] for value in values if value["kind"] == "medication"] == [
        medication_id
    ]
    assert all(value["kind"] not in NEW_RECORD_KINDS for value in values)
    assert all(item.evidence_type not in NEW_RECORD_KINDS for item in evidence)


def test_live_chat_projection_includes_confirmed_new_records_with_read_scopes(
    product_runtime: object,
) -> None:
    for fact_type in ("procedure", "recommendation", "follow_up"):
        _confirm_new_record(product_runtime, "person-1", fact_type)

    evidence, values = current_live_chat_evidence(
        product_runtime, "person-1", NOW, read_scopes=NEW_RECORD_READ_SCOPES
    )
    by_kind = {value["kind"]: value for value in values if value["kind"] in NEW_RECORD_KINDS}

    assert sorted(by_kind) == ["follow_up", "procedure", "recommendation"]
    assert len(evidence) == len(values)
    assert all(item.provenance_status == "source_backed" for item in evidence)
    assert all(item.source_ids for item in evidence)
