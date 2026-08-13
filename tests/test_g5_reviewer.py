"""Focused reviewer-route tests (G5, Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.g5.report import REPORT_SCHEMA_VERSION, serialize_report
from evals.g5_review import run_review


@pytest.fixture(scope="module")
def review_result(tmp_path_factory: pytest.TempPathFactory):
    report_dir = tmp_path_factory.mktemp("g5-report")
    exit_code, report = run_review(write=True, report_dir=report_dir)
    return exit_code, report, report_dir


def test_reviewer_exit_code_is_zero_and_state_is_not_blocked(review_result) -> None:
    exit_code, report, _ = review_result
    assert exit_code == 0
    assert report["summary"]["state"] in {"PASS", "READY_FOR_SECOND_CLIENT_SMOKE"}


def test_reviewer_report_has_versioned_shape(review_result) -> None:
    _, report, _ = review_result
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["summary"]["total_cases"] == 20
    assert report["summary"]["passed_cases"] == 20
    assert report["summary"]["failed_cases"] == 0
    assert report["summary"]["deterministic_replay"] == "pass"
    assert report["summary"]["plugin_integrity"] == "pass"


def test_reviewer_security_invariants_all_zero(review_result) -> None:
    _, report, _ = review_result
    for name, count in report["security_invariants"].items():
        assert count == 0, f"{name} = {count}"


def test_reviewer_writes_report_file(review_result) -> None:
    _, report, report_dir = review_result
    written = report_dir / "g5-review.json"
    assert written.is_file()
    parsed = json.loads(written.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == REPORT_SCHEMA_VERSION


def test_report_schema_conforms_to_committed_schema() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "evals" / "g5" / "report.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"] == "opencare-g5-eval/1"
    # A minimal report passes the committed schema's top-level required fields.
    minimal = {
        "schema_version": "opencare-g5-eval/1",
        "generated_at": "2027-08-02T10:00:00+00:00",
        "summary": {
            "state": "PASS",
            "total_cases": 20,
            "passed_cases": 20,
            "failed_cases": 0,
            "deterministic_replay": "pass",
            "plugin_integrity": "pass",
            "cross_client": {},
        },
        "security_invariants": {
            "unauthorized_evidence_exposures": 0,
            "external_calls_without_consent": 0,
            "canonical_mutations_via_agent_path": 0,
            "provider_calls_after_revocation": 0,
            "provider_calls_after_context_change": 0,
            "accepted_invalid_citations": 0,
            "accepted_unsupported_prescriptive_claims": 0,
            "receipt_verification_failures_for_valid_receipts": 0,
        },
        "quality_metrics": {},
        "cases": [],
    }
    assert serialize_report(minimal).startswith(b"{")
