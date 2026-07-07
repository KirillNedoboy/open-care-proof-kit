import pytest

from app.health_vault.loader import load_demo_family_vault
from app.health_vault.trace_graph import build_vault_trace_graph


def test_trace_graph_builds_from_demo_family_vault() -> None:
    graph = build_vault_trace_graph(load_demo_family_vault())

    assert graph.summary.demo_only is True
    assert graph.summary.synthetic is True
    assert graph.summary.no_llm_generation is True
    assert graph.summary.no_genetics is True
    assert graph.summary.no_medical_advice is True
    assert graph.summary.node_count > 0
    assert graph.summary.edge_count > 0


def test_trace_graph_includes_all_synthetic_people_sources_and_artifacts() -> None:
    graph = build_vault_trace_graph(load_demo_family_vault())

    people_labels = {
        node.label for node in graph.nodes if node.node_type == "person"
    }
    source_labels = {
        node.label for node in graph.nodes if node.node_type == "document_source"
    }
    artifact_labels = {
        node.label for node in graph.nodes if node.node_type == "artifact"
    }

    assert people_labels == {"Demo Adult Alex", "Demo Adult Jordan", "Demo Teen Sam"}
    assert "Synthetic primary care note, January 2026" in source_labels
    assert "Synthetic lab panel, February 2026" in source_labels
    assert "Synthetic medication list, March 2026" in source_labels
    assert artifact_labels == {
        "family-vault-read-model.json",
        "family-vault-summary.md",
        "family-vault-manifest.json",
    }


def test_every_important_record_node_has_a_source_edge() -> None:
    graph = build_vault_trace_graph(load_demo_family_vault())

    linked_source_targets = {
        edge.from_node_id
        for edge in graph.edges
        if edge.edge_type == "linked_to_source"
    }
    important_record_nodes = {
        node.id
        for node in graph.nodes
        if node.node_type
        in {
            "recorded_medication",
            "recorded_condition",
            "recorded_lab",
            "visit",
            "timeline_event",
            "question_thread",
        }
    }

    assert important_record_nodes
    assert important_record_nodes <= linked_source_targets
    assert graph.summary.source_linked_record_count == len(important_record_nodes)
    assert graph.summary.missing_source_record_count == 0


def test_trace_graph_includes_safety_boundary_summary() -> None:
    graph = build_vault_trace_graph(load_demo_family_vault())

    safety_nodes = [node for node in graph.nodes if node.node_type == "safety_boundary"]

    assert graph.summary.safety_boundary_count >= 1
    assert safety_nodes
    assert any(node.label == "OpenCare does not diagnose." for node in safety_nodes)


def test_trace_graph_fails_closed_for_missing_provenance() -> None:
    dataset = load_demo_family_vault()
    invalid_lab = dataset.lab_results[0].model_copy(update={"evidence": []})
    invalid_dataset = dataset.model_copy(
        update={"lab_results": [invalid_lab, *dataset.lab_results[1:]]}
    )

    with pytest.raises(ValueError, match="provenance"):
        build_vault_trace_graph(invalid_dataset)


def test_trace_graph_fails_closed_for_unsafe_text() -> None:
    dataset = load_demo_family_vault()
    unsafe_condition = dataset.conditions[0].model_copy(
        update={"description": "OpenCare diagnosis: insomnia."}
    )
    invalid_dataset = dataset.model_copy(
        update={"conditions": [unsafe_condition, *dataset.conditions[1:]]}
    )

    with pytest.raises(ValueError, match="unsafe"):
        build_vault_trace_graph(invalid_dataset)


def test_trace_graph_does_not_emit_forbidden_capability_wording() -> None:
    graph = build_vault_trace_graph(load_demo_family_vault())
    rendered = graph.model_dump_json().lower()

    assert "opencare diagnosis" not in rendered
    assert "diagnosed by opencare" not in rendered
    assert "medication selection advice" not in rendered
    assert "clinical decision support" not in rendered
    assert "start taking" not in rendered
    assert "stop taking" not in rendered
