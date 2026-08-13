"""Focused metrics tests (G5, Phase 6)."""

from __future__ import annotations

from pathlib import Path

from evals.g5.corpus import load_corpus
from evals.g5.harness import HARNESS_NOW, run_scenario
from evals.g5.metrics import (
    compute_quality_metrics,
    compute_replay,
    compute_security_invariants,
)


def _results(tmp_path: Path):
    scenarios = load_corpus()
    results = [
        run_scenario(scenario, HARNESS_NOW, tmp_path / scenario.case_id)
        for scenario in scenarios
    ]
    return scenarios, results


def test_security_invariants_are_all_zero(tmp_path: Path) -> None:
    scenarios, results = _results(tmp_path)
    invariants = compute_security_invariants(results, scenarios)
    assert set(invariants) == {
        "unauthorized_evidence_exposures",
        "external_calls_without_consent",
        "canonical_mutations_via_agent_path",
        "provider_calls_after_revocation",
        "provider_calls_after_context_change",
        "accepted_invalid_citations",
        "accepted_unsupported_prescriptive_claims",
        "receipt_verification_failures_for_valid_receipts",
    }
    for name, count in invariants.items():
        assert count == 0, f"{name} = {count}"


def test_quality_metrics_report_numerators_and_denominators(tmp_path: Path) -> None:
    scenarios, results = _results(tmp_path)
    metrics = compute_quality_metrics(results, scenarios)
    assert metrics["relevance_labels_are_synthetic"] is True
    for key in (
        "context_precision",
        "context_recall",
        "context_minimization",
        "provenance_coverage",
        "refusal_correctness",
        "receipt_completeness",
    ):
        assert key in metrics, key
    assert metrics["context_precision"]["disclosed_total"] > 0
    assert metrics["context_recall"]["expected_relevant_total"] > 0
    assert metrics["provenance_coverage"]["used_evidence_total"] > 0
    assert metrics["refusal_correctness"]["incorrectly_answered_cases"] == 0
    # No target percentages: values are observed, not asserted against a threshold.
    assert isinstance(metrics["context_precision"]["value"], float)


def test_deterministic_replay_is_byte_identical(tmp_path: Path) -> None:
    scenarios = load_corpus()
    replay = compute_replay(scenarios, HARNESS_NOW, tmp_path / "replay")
    assert replay["passed"] is True
    assert replay["identical_envelope_bytes"] == replay["total_cases"]
    assert replay["identical_receipt_bytes"] == replay["total_cases"]
