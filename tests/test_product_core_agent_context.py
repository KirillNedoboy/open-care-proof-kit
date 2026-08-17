from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agent.context import build_product_core_agent_context
from app.config import clear_settings_cache, load_settings
from app.product_core.models import Person
from app.product_core.runtime import create_product_core_runtime


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"ctx-id-{self.value}"


@pytest.fixture
def product_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    monkeypatch.setenv("OPENCARE_PRODUCT_DB_PATH", str(tmp_path / "product" / "db.sqlite3"))
    monkeypatch.setenv("OPENCARE_SOURCE_DIR", str(tmp_path / "product" / "sources"))
    monkeypatch.setenv("OPENCARE_SESSION_DB_PATH", str(tmp_path / "runtime" / "sessions.sqlite3"))
    monkeypatch.setenv("OPENCARE_ENV", "development")
    monkeypatch.setenv("OPENCARE_DEMO_MODE", "true")
    clear_settings_cache()
    clock = FixedClock(datetime(2026, 8, 2, 12, tzinfo=UTC))
    ids = SequenceIds()
    runtime = create_product_core_runtime(
        load_settings(None), clock=clock, id_factory=ids
    )
    runtime.database.migrate()
    with runtime.database.uow() as uow:
        for person_id in ("person-1", "person-2"):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=f"Profile {person_id}",
                    created_at=clock(),
                    updated_at=clock(),
                    is_active=True,
                )
            )
    yield runtime
    clear_settings_cache()


def _confirm_medication(runtime: object, person_id: str, name: str) -> str:
    source = runtime.sources.register_manual_entry(person_id, name)
    candidate = runtime.lifecycle.create_candidate(
        person_id=person_id, source_id=source.id, display_name=name
    )
    return runtime.lifecycle.confirm(candidate.id).id


def _confirm_condition(runtime: object, person_id: str, name: str, status_text: str | None) -> str:
    from app.product_core.models import ConditionCandidateInput

    source = runtime.sources.register_structured_manual_entry(
        person_id, "condition", {"display_name": name, "status_text": status_text}
    )
    candidate = runtime.lifecycle.create_fact_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name=name, status_text=status_text),
    )
    return runtime.lifecycle.confirm(candidate.id).id


def _confirm_lab(
    runtime: object,
    person_id: str,
    test_name: str,
    result_text: str,
    source_flag_text: str | None,
) -> str:
    from app.product_core.models import LabCandidateInput

    source = runtime.sources.register_structured_manual_entry(
        person_id,
        "lab",
        {"test_name": test_name, "result_text": result_text, "source_flag_text": source_flag_text},
    )
    candidate = runtime.lifecycle.create_fact_candidate(
        person_id=person_id,
        source_id=source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(
            test_name=test_name,
            result_text=result_text,
            source_flag_text=source_flag_text,
        ),
    )
    return runtime.lifecycle.confirm(candidate.id).id


def test_context_includes_confirmed_condition_and_lab_evidence(
    product_runtime: object,
) -> None:
    _confirm_medication(product_runtime, "person-1", "Aspirin")
    _confirm_condition(product_runtime, "person-1", "Asthma", "chronic")
    _confirm_lab(product_runtime, "person-1", "Hemoglobin", "13.8", "H")

    context = build_product_core_agent_context(product_runtime, "person-1")
    by_kind: dict[str, list[object]] = {}
    for item in context.items:
        by_kind.setdefault(item.kind, []).append(item)

    condition = by_kind["condition"][0]
    assert condition.id
    assert "Asthma" in condition.text
    assert "chronic" in condition.text
    assert condition.source_ids
    assert condition.provenance_status == "source_backed"

    lab = by_kind["lab"][0]
    assert "Hemoglobin" in lab.text
    assert "13.8" in lab.text
    assert "flag H (as reported)" in lab.text
    assert lab.source_ids
    assert lab.provenance_status == "source_backed"

    assert any(item.kind == "medication" for item in context.items)


def test_context_excludes_pending_rejected_unsupported_and_superseded(
    product_runtime: object,
) -> None:
    from app.product_core.models import ConditionCandidateInput, LabCandidateInput

    # Pending condition candidate (never reviewed).
    pending_source = product_runtime.sources.register_structured_manual_entry(
        "person-1", "condition", {"display_name": "Eczema"}
    )
    product_runtime.lifecycle.create_fact_candidate(
        person_id="person-1",
        source_id=pending_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Eczema"),
    )
    # Rejected lab candidate.
    rejected_source = product_runtime.sources.register_structured_manual_entry(
        "person-1", "lab", {"test_name": "Glucose", "result_text": "95"}
    )
    rejected = product_runtime.lifecycle.create_fact_candidate(
        person_id="person-1",
        source_id=rejected_source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(test_name="Glucose", result_text="95"),
    )
    product_runtime.lifecycle.reject(rejected.id)
    # Unsupported condition candidate.
    unsupported_source = product_runtime.sources.register_structured_manual_entry(
        "person-1", "condition", {"display_name": "Unsupported"}
    )
    unsupported = product_runtime.lifecycle.create_fact_candidate(
        person_id="person-1",
        source_id=unsupported_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Unsupported"),
    )
    product_runtime.lifecycle.unsupported(unsupported.id)
    # Confirmed then superseded condition: only the ACTIVE canonical appears.
    source = product_runtime.sources.register_structured_manual_entry(
        "person-1", "condition", {"display_name": "Asthma"}
    )
    candidate = product_runtime.lifecycle.create_fact_candidate(
        person_id="person-1",
        source_id=source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Asthma"),
    )
    product_runtime.lifecycle.confirm(candidate.id)
    correction_source = product_runtime.sources.register_structured_manual_entry(
        "person-1", "condition", {"display_name": "Asthma (seasonal)"}
    )
    replacement = product_runtime.lifecycle.correct_fact_candidate(
        candidate.id,
        detail_input=ConditionCandidateInput(display_name="Asthma (seasonal)"),
        source_id=correction_source.id,
    )
    product_runtime.lifecycle.confirm(replacement.id)

    context = build_product_core_agent_context(product_runtime, "person-1")
    condition_items = [item for item in context.items if item.kind == "condition"]
    lab_items = [item for item in context.items if item.kind == "lab"]

    assert [item.text for item in condition_items] == ["Asthma (seasonal)"]
    assert lab_items == []


def test_context_excludes_other_person_records(product_runtime: object) -> None:
    _confirm_condition(product_runtime, "person-1", "Asthma", None)
    _confirm_lab(product_runtime, "person-2", "Glucose", "95", None)

    context = build_product_core_agent_context(product_runtime, "person-1")

    assert [item.kind for item in context.items if item.kind == "lab"] == []
    assert any(item.kind == "condition" for item in context.items)
    assert all(
        item.kind != "condition" or "Asthma" in item.text for item in context.items
    )
