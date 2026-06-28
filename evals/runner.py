import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.demo_pipeline import build_demo_briefing
from evals.metrics import EvalResult, EvalSummary

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "evals" / "cases"
RESULTS_DIR = ROOT / "evals" / "results"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    mode: Literal["static_text", "pipeline"] = "static_text"
    text: str = ""
    drug: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)
    must_include_report: list[str] = Field(default_factory=list)
    must_not_include_report: list[str] = Field(default_factory=list)
    must_match_audit: dict[str, Any] = Field(default_factory=dict)


def get_nested_value(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(path)
        value = value[part]
    return value


def load_cases(cases_dir: Path = CASES_DIR) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(cases_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cases.append(EvalCase.model_validate(raw))
        except ValueError as exc:
            raise ValueError(f"Invalid eval case {path.name}: {exc}") from exc

    return cases


def evaluate_text_case(case: EvalCase) -> EvalResult:
    text = case.text.lower()
    failures: list[str] = []

    for phrase in case.must_include:
        if phrase.lower() not in text:
            failures.append(f"missing required phrase: {phrase}")

    for phrase in case.must_not_include:
        if phrase.lower() in text:
            failures.append(f"forbidden phrase found: {phrase}")

    return EvalResult(case_id=case.case_id, passed=not failures, failures=failures)


def evaluate_pipeline_case(case: EvalCase) -> EvalResult:
    result = build_demo_briefing(case.drug)
    report_text = result.report_markdown.lower()
    failures: list[str] = []

    for phrase in case.must_include_report:
        if phrase.lower() not in report_text:
            failures.append(f"missing required report phrase: {phrase}")

    for phrase in case.must_not_include_report:
        if phrase.lower() in report_text:
            failures.append(f"forbidden report phrase found: {phrase}")

    for path, expected in case.must_match_audit.items():
        try:
            actual = get_nested_value(result.audit, path)
        except KeyError:
            failures.append(f"missing audit path: {path}")
            continue
        if actual != expected:
            failures.append(
                f"audit mismatch for {path}: expected {expected!r}, got {actual!r}"
            )

    return EvalResult(case_id=case.case_id, passed=not failures, failures=failures)


def evaluate_case(case: EvalCase) -> EvalResult:
    if case.mode == "pipeline":
        return evaluate_pipeline_case(case)
    return evaluate_text_case(case)


def run_evals(cases_dir: Path = CASES_DIR) -> EvalSummary:
    cases = load_cases(cases_dir)
    results = [evaluate_case(case) for case in cases]
    total_cases = len(results)
    total = max(total_cases, 1)
    failed = [result for result in results if not result.passed]
    pipeline_cases = sum(1 for case in cases if case.mode == "pipeline")
    static_text_cases = total_cases - pipeline_cases
    pipeline_failed = [
        result
        for case, result in zip(cases, results, strict=False)
        if case.mode == "pipeline" and not result.passed
    ]

    unsafe_failures = sum(
        1
        for result in failed
        for failure in result.failures
        if "forbidden phrase" in failure
    )
    missing_source_failures = sum(
        1
        for result in failed
        for failure in result.failures
        if "source" in failure.lower()
    )
    uncertainty_failures = sum(
        1
        for result in failed
        for failure in result.failures
        if "uncertain" in failure.lower() or "limitations" in failure.lower()
    )
    audit_failures = sum(
        1
        for result in failed
        for failure in result.failures
        if "audit" in failure.lower()
    )

    return EvalSummary(
        total_cases=total_cases,
        static_text_cases=static_text_cases,
        pipeline_cases=pipeline_cases,
        passed_cases=sum(1 for result in results if result.passed),
        failed_cases=len(failed),
        unsafe_advice_rate=unsafe_failures / total,
        missing_source_rate=missing_source_failures / total,
        uncertainty_missing_rate=uncertainty_failures / total,
        audit_missing_rate=audit_failures / total,
        pipeline_failure_rate=(
            len(pipeline_failed) / pipeline_cases if pipeline_cases else 0.0
        ),
        results=results,
    )


def main() -> None:
    summary = run_evals()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "latest.json"
    output_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    print(summary.model_dump_json(indent=2))
    if summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
