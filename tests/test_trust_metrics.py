from pathlib import Path

from evals.runner import run_evals
from evals.trust_metrics import build_trust_metrics_report


def test_trust_metrics_report_contains_eval_metric_names() -> None:
    report = build_trust_metrics_report()

    for metric_name in [
        "total_cases",
        "static_text_cases",
        "pipeline_cases",
        "passed_cases",
        "failed_cases",
        "unsafe_advice_rate",
        "missing_source_rate",
        "uncertainty_missing_rate",
        "audit_missing_rate",
        "pipeline_failure_rate",
    ]:
        assert metric_name in report


def test_trust_metrics_report_contains_artifact_safety_flags() -> None:
    report = build_trust_metrics_report()

    for flag in [
        "demo_only: true",
        "synthetic: true",
        "no_llm_generation: true",
        "no_genetics: true",
        "no_medical_advice: true",
        "provenance_complete: true",
    ]:
        assert flag in report


def test_trust_metrics_report_keeps_medical_boundaries() -> None:
    report = build_trust_metrics_report().lower()

    assert "not clinical validation" in report
    assert "not medical advice" in report
    assert "not diagnosis" in report
    assert "clinically safe" not in report


def test_missing_manifest_reports_unavailable_safely(tmp_path: Path) -> None:
    report = build_trust_metrics_report(
        manifest_path=tmp_path / "missing-manifest.json"
    )

    assert "manifest_status: unavailable" in report
    assert "provenance_complete: unavailable" in report
    assert "not clinical validation" in report


def test_existing_evals_runner_still_passes() -> None:
    summary = run_evals()

    assert summary.passed_cases == summary.total_cases
    assert summary.failed_cases == 0
