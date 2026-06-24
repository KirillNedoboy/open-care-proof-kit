import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from evals.metrics import EvalResult, EvalSummary

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "evals" / "cases"
RESULTS_DIR = ROOT / "evals" / "results"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    text: str = ""
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)


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


def run_evals(cases_dir: Path = CASES_DIR) -> EvalSummary:
    results = [evaluate_text_case(case) for case in load_cases(cases_dir)]
    total = max(len(results), 1)
    failed = [result for result in results if not result.passed]

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
        passed_cases=sum(1 for result in results if result.passed),
        failed_cases=len(failed),
        unsafe_advice_rate=unsafe_failures / total,
        missing_source_rate=missing_source_failures / total,
        uncertainty_missing_rate=uncertainty_failures / total,
        audit_missing_rate=audit_failures / total,
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
