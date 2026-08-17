"""Focused pytest for the deterministic P1 reviewer (``evals.p1_review``).

The reviewer builds its own temporary database/sources and is fully offline;
the test invokes it once as a subprocess and asserts the exit code and verdict
without re-running the scenario in-process.
"""

from __future__ import annotations

import subprocess
import sys


def test_p1_reviewer_passes_and_prints_pass() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "evals.p1_review"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "P1 REVIEW" in result.stdout
    assert "result: PASS" in result.stdout
    for counter in (
        "canonical_without_review",
        "canonical_without_source",
        "cross_person_record_exposure",
        "cross_person_source_exposure",
        "unauthorized_confirmation",
        "provenance_mismatch_accepted",
    ):
        assert f"counter {counter}: 0" in result.stdout
