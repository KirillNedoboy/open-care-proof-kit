from pathlib import Path

import pytest

from evals.runner import run_evals


def test_evals_runner_passes_initial_cases() -> None:
    summary = run_evals()
    assert summary.failed_cases == 0
    assert summary.passed_cases >= 1


def test_evals_runner_rejects_invalid_case_schema(tmp_path: Path) -> None:
    case_path = tmp_path / "invalid.json"
    case_path.write_text('{"text": "not medical advice"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid eval case"):
        run_evals(cases_dir=tmp_path)
