"""Focused pytest coverage for the deterministic P2 reviewer.

The reviewer owns its temporary SQLite/source fixtures and must remain fully
offline. This test checks the observable verdict and the security accounting
rather than reaching into its implementation details.
"""

from __future__ import annotations

import subprocess
import sys

REQUIRED_PASS_LINES = (
    "P2 REVIEW",
    "capabilities: pass",
    "person isolation: pass",
    "review workflow: pass",
    "records/current-history: pass",
    "provenance: pass",
    "timeline: pass",
    "visit preparation: pass",
    "revocation: pass",
    "export version: pass",
    "result: PASS",
)

COUNTERS = (
    "cross_person_workspace_exposures",
    "stale_person_render_acceptances",
    "unauthorized_ui_backed_mutations",
    "hidden_record_count_exposures",
    "hidden_source_metadata_exposures",
    "legacy_scope_expansions",
)


def test_p2_reviewer_is_deterministic_and_zero_exposure() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "evals.p2_review"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    for line in REQUIRED_PASS_LINES:
        assert line in result.stdout
    for counter in COUNTERS:
        assert f"counter {counter}: 0" in result.stdout
    assert result.stderr == ""
