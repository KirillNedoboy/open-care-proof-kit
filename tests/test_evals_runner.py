import json
from pathlib import Path

import pytest

from evals.runner import EvalCase, evaluate_case, load_cases, run_evals


def test_evals_runner_passes_initial_cases() -> None:
    summary = run_evals()
    assert summary.failed_cases == 0
    assert summary.passed_cases >= 1


def test_evals_runner_rejects_invalid_case_schema(tmp_path: Path) -> None:
    case_path = tmp_path / "invalid.json"
    case_path.write_text('{"text": "not medical advice"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid eval case"):
        run_evals(cases_dir=tmp_path)


def test_eval_suite_includes_phase_14_evidence_cases() -> None:
    case_ids = {case.case_id for case in load_cases()}

    assert "unsupported_drug_no_claim" in case_ids
    assert "no_source_no_claim" in case_ids
    assert "demo_only_disclosure_required" in case_ids
    assert "coverage_limitations_required" in case_ids


def test_static_text_eval_mode_still_passes() -> None:
    case = EvalCase(
        case_id="static-case",
        mode="static_text",
        text="Not medical advice. Sources and limitations are present. Audit metadata.",
        must_include=["not medical advice", "sources", "limitations", "audit"],
        must_not_include=["increase dose"],
    )

    result = evaluate_case(case)

    assert result.passed is True


def test_pipeline_eval_calls_build_demo_briefing(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    class DummyResult:
        report_markdown = "Not medical advice. Demo evidence-pack coverage. Sources. Limitations."
        audit = {
            "policy_passed": True,
            "coverage": {"coverage_status": "matched_demo_rule", "matched_findings": 1},
            "raw_health_or_genetic_data_exported": False,
        }

    def fake_build_demo_briefing(drug: str) -> DummyResult:
        called.append(drug)
        return DummyResult()

    monkeypatch.setattr("evals.runner.build_demo_briefing", fake_build_demo_briefing)
    case = EvalCase(
        case_id="pipeline-sertraline",
        mode="pipeline",
        drug="sertraline",
        must_include_report=["not medical advice"],
        must_match_audit={"policy_passed": True},
    )

    result = evaluate_case(case)

    assert result.passed is True
    assert called == ["sertraline"]


def test_pipeline_unsupported_drug_eval_passes_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResult:
        report_markdown = (
            "Not medical advice. No demo evidence-pack rules exist for this drug. "
            "The report makes no clinical claim."
        )
        audit = {
            "policy_passed": True,
            "coverage": {"coverage_status": "drug_not_in_demo_pack", "matched_findings": 0},
            "raw_health_or_genetic_data_exported": False,
        }

    monkeypatch.setattr(
        "evals.runner.build_demo_briefing",
        lambda drug: DummyResult(),
    )
    case = EvalCase(
        case_id="pipeline-aspirin",
        mode="pipeline",
        drug="aspirin",
        must_include_report=["no demo evidence-pack rules", "not medical advice"],
        must_not_include_report=["increase dose"],
        must_match_audit={
            "policy_passed": True,
            "coverage.coverage_status": "drug_not_in_demo_pack",
            "coverage.matched_findings": 0,
            "raw_health_or_genetic_data_exported": False,
        },
    )

    result = evaluate_case(case)

    assert result.passed is True


def test_pipeline_eval_nested_audit_path_matching_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResult:
        report_markdown = "Not medical advice. Sources. Limitations."
        audit = {
            "policy_passed": True,
            "coverage": {
                "coverage_status": "matched_demo_rule",
                "matched_findings": 1,
            },
        }

    monkeypatch.setattr(
        "evals.runner.build_demo_briefing",
        lambda drug: DummyResult(),
    )
    case = EvalCase(
        case_id="nested-audit",
        mode="pipeline",
        drug="sertraline",
        must_match_audit={
            "coverage.coverage_status": "matched_demo_rule",
            "coverage.matched_findings": 1,
        },
    )

    result = evaluate_case(case)

    assert result.passed is True


def test_eval_runner_result_json_contains_static_and_pipeline_counts(tmp_path: Path) -> None:
    static_case = {
        "case_id": "static",
        "mode": "static_text",
        "text": "Not medical advice. Sources. Limitations. Audit.",
        "must_include": ["not medical advice", "sources", "limitations", "audit"],
    }
    pipeline_case = {
        "case_id": "pipeline",
        "mode": "pipeline",
        "drug": "aspirin",
        "must_include_report": ["not medical advice"],
        "must_match_audit": {
            "policy_passed": True,
            "coverage.coverage_status": "drug_not_in_demo_pack",
            "coverage.matched_findings": 0,
            "raw_health_or_genetic_data_exported": False,
        },
    }
    (tmp_path / "static.json").write_text(json.dumps(static_case), encoding="utf-8")
    (tmp_path / "pipeline.json").write_text(json.dumps(pipeline_case), encoding="utf-8")

    summary = run_evals(cases_dir=tmp_path)

    assert summary.total_cases == 2
    assert summary.static_text_cases == 1
    assert summary.pipeline_cases == 1
