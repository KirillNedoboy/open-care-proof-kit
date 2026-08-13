"""Deterministic machine-readable G5 reviewer report.

The report format is versioned (``opencare-g5-eval/1``) and committed here as a
documented structure plus ``report.schema.json``. Generated reports are written
to ``reports/g5/`` (gitignored); the committed reviewer-safe example lives next
to this module (``example-report.json``).

The report carries **no** raw health data, prompts with secrets, filesystem
usernames, session tokens, DB paths, or API credentials — the corpus is
synthetic-only and the only timestamps are fixed synthetic values.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

REPORT_SCHEMA_VERSION = "opencare-g5-eval/1"

#: Fixed synthetic timestamp so reports are byte-deterministic across runs.
REPORT_TIMESTAMP = datetime(2027, 8, 2, 10, 0, 0, tzinfo=UTC)

ReportState = Literal["PASS", "READY_FOR_SECOND_CLIENT_SMOKE", "BLOCKED"]


def default_report_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "reports" / "g5"


def build_report(
    *,
    state: ReportState,
    total_cases: int,
    passed_cases: int,
    failed_cases: int,
    security_invariants: dict[str, int],
    quality_metrics: dict[str, Any],
    cases: list[dict[str, Any]],
    replay: dict[str, Any],
    plugin_integrity: dict[str, Any],
    cross_client: dict[str, Any],
    generated_at: datetime = REPORT_TIMESTAMP,
) -> dict[str, Any]:
    """Assemble the versioned report document (deterministic key order)."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "summary": {
            "state": state,
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "deterministic_replay": "pass" if replay.get("passed") else "fail",
            "plugin_integrity": "pass" if plugin_integrity.get("passed") else "fail",
            "cross_client": cross_client,
        },
        "security_invariants": security_invariants,
        "quality_metrics": quality_metrics,
        "cases": cases,
    }


def serialize_report(report: dict[str, Any]) -> bytes:
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def write_report(report: dict[str, Any], output_dir: Path | None = None) -> Path:
    directory = output_dir if output_dir is not None else default_report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "g5-review.json"
    target.write_bytes(serialize_report(report))
    return target


__all__ = [
    "REPORT_SCHEMA_VERSION",
    "REPORT_TIMESTAMP",
    "ReportState",
    "build_report",
    "default_report_dir",
    "serialize_report",
    "write_report",
]
