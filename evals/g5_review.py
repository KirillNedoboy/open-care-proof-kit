"""Sentient G5 local reviewer (``python -m evals.g5_review``).

The single offline, deterministic reviewer entry point. It verifies the G4
schemas/fixtures, runs the 20-case adversarial corpus against the real
``G2Runtime``, computes the security invariants and observational metrics,
recomputes the Agent Plugin package identity, validates any committed
cross-client evidence records, prints a concise summary, and (optionally)
writes the machine-readable report to ``reports/g5/``.

It never touches the network, Ollama, Sentient, an external model, a browser,
real health data, or Docker, and it never runs the full pytest suite.

Exit codes: ``0`` pass (or ``READY_FOR_SECOND_CLIENT_SMOKE``), ``1`` a
P0/P1 defect (``BLOCKED``), ``2`` usage error.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from app.agent_trust.fixtures import default_fixtures_dir, generate_fixtures
from app.agent_trust.schemas import default_schema_dir, generate_schemas
from evals.g5.corpus import load_corpus
from evals.g5.harness import HARNESS_NOW, run_scenario
from evals.g5.metrics import (
    compute_quality_metrics,
    compute_replay,
    compute_security_invariants,
)
from evals.g5.plugin import (
    PLUGIN_DIR,
    REQUIRED_SKILLS,
    normalize_bytes,
    plugin_tree_hash,
    verify_plugin_integrity,
)
from evals.g5.report import (
    REPORT_TIMESTAMP,
    ReportState,
    build_report,
    write_report,
)

CROSS_CLIENT_DIR = PLUGIN_DIR.parents[1] / "docs" / "evals" / "g5-cross-client"


def _verify_schemas() -> tuple[bool, list[str]]:
    failures: list[str] = []
    generated = generate_schemas()
    sdir = default_schema_dir()
    for name, content in generated.items():
        committed = normalize_bytes((sdir / name).read_bytes())
        if committed != normalize_bytes(content):
            failures.append(f"schema {name} drifted from the contract models")
    return not failures, failures


def _verify_fixtures() -> tuple[bool, list[str]]:
    failures: list[str] = []
    generated = generate_fixtures()
    fdir = default_fixtures_dir()
    for name, content in generated.items():
        committed = normalize_bytes((fdir / name).read_bytes())
        if committed != normalize_bytes(content):
            failures.append(f"fixture {name} drifted from the trusted builders")
    return not failures, failures


def _validate_cross_client() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    if not CROSS_CLIENT_DIR.is_dir():
        return {"clients": 0, "status": "pending", "records": records, "passed": True}

    committed_hash = plugin_tree_hash()
    for path in sorted(CROSS_CLIENT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            records.append({"file": path.name, "error": "unreadable", "passed": False})
            continue
        if not isinstance(data, dict):
            records.append({"file": path.name, "error": "not an object", "passed": False})
            continue
        client = data.get("client") or data.get("client_id")
        package_hash = data.get("package_hash") or data.get("package_tree_hash")
        skills = data.get("skills") or data.get("discovered_skills")
        problems: list[str] = []
        if not isinstance(client, str) or not client:
            problems.append("missing client identity")
        if package_hash is not None and package_hash != committed_hash:
            problems.append("package hash does not match the committed package")
        if isinstance(skills, list):
            missing = set(REQUIRED_SKILLS) - set(skills)
            if missing:
                problems.append(f"missing skills: {sorted(missing)}")
        records.append(
            {
                "file": path.name,
                "client": client,
                "passed": not problems,
                "problems": problems,
            }
        )

    valid = [record for record in records if record.get("passed")]
    clients = {
        record.get("client") for record in valid if isinstance(record.get("client"), str)
    }
    return {
        "clients": len(clients),
        "status": "validated",
        "records": records,
        "passed": len(clients) >= 2,
    }


def run_review(
    *, write: bool = False, report_dir: Path | None = None
) -> tuple[int, dict[str, Any]]:
    scenarios = load_corpus()
    failures: list[str] = []

    schemas_ok, schema_failures = _verify_schemas()
    fixtures_ok, fixture_failures = _verify_fixtures()
    failures.extend(f"schema: {failure}" for failure in schema_failures)
    failures.extend(f"fixture: {failure}" for failure in fixture_failures)

    tmp_root = Path(tempfile.mkdtemp(prefix="g5-review-"))
    results = [
        run_scenario(scenario, HARNESS_NOW, tmp_root / scenario.case_id)
        for scenario in scenarios
    ]

    invariants = compute_security_invariants(results, scenarios)
    quality = compute_quality_metrics(results, scenarios)
    replay = compute_replay(scenarios, HARNESS_NOW, tmp_root / "replay")

    plugin = verify_plugin_integrity(PLUGIN_DIR, tmp_root=tmp_root / "plugin")
    cross_client = _validate_cross_client()

    for name, count in invariants.items():
        if count != 0:
            failures.append(f"security invariant {name} = {count} (expected 0)")
    for result in results:
        if not result.passed:
            failures.append(f"case {result.case_id} failed: {result.failures}")
    if not schemas_ok:
        failures.append("schema verification failed")
    if not fixtures_ok:
        failures.append("fixture verification failed")
    # Three-state verdict.
    if failures:
        state: ReportState = "BLOCKED"
    elif cross_client["clients"] >= 2:
        state = "PASS"
    else:
        state = "READY_FOR_SECOND_CLIENT_SMOKE"
    passed_cases = sum(1 for result in results if result.passed)
    total_cases = len(results)

    # Three-state verdict.
    if failures or not cross_client["passed"]:
        state = "BLOCKED"
    elif cross_client["clients"] >= 2:
        state = "PASS"
    else:
        state = "READY_FOR_SECOND_CLIENT_SMOKE"

    cases = [
        {
            "case_id": result.case_id,
            "category": result.category,
            "passed": result.passed,
            "outcome": result.outcome,
            "reason_codes": result.reason_codes,
            "provider_calls": result.provider_calls,
        }
        for result in results
    ]

    report = build_report(
        state=state,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=total_cases - passed_cases,
        security_invariants=invariants,
        quality_metrics=quality,
        cases=cases,
        replay=replay,
        plugin_integrity=plugin,
        cross_client=cross_client,
        generated_at=REPORT_TIMESTAMP,
    )
    if write:
        write_report(report, report_dir)

    exit_code = 1 if state == "BLOCKED" else 0
    return exit_code, report


def _print_summary(exit_code: int, report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("G5 REVIEW")
    print(
        f"cases: {summary['passed_cases']}/{summary['total_cases']} passed"
        f" (state: {summary['state']})"
    )
    for name, count in report["security_invariants"].items():
        print(f"{name}: {count}")
    print(f"deterministic replay: {summary['deterministic_replay']}")
    print(f"portable plugin integrity: {summary['plugin_integrity']}")
    print(f"schema_version: {report['schema_version']}")
    if report["quality_metrics"]:
        q = report["quality_metrics"]
        precision = _fmt(q["context_precision"]["value"])
        recall = _fmt(q["context_recall"]["value"])
        provenance = _fmt(q["provenance_coverage"]["value"])
        refused = q["refusal_correctness"]["correctly_refused_cases"]
        expected = q["refusal_correctness"]["expected_refusal_cases"]
        print(
            f"quality: precision={precision} recall={recall} provenance={provenance} "
            f"refusal={refused}/{expected}"
        )
    if exit_code != 0:
        print(f"verdict: BLOCKED (exit {exit_code})")
        for name, count in report["security_invariants"].items():
            if count != 0:
                print(f"  FAILED invariant {name}: {count}")


def _fmt(value: Any) -> str:
    return "unavailable" if value is None else f"{value:.4f}"


def _print_json(report: dict[str, Any]) -> None:
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.g5_review",
        description="Sentient G5 offline ecosystem-validation reviewer.",
    )
    parser.add_argument("--write", action="store_true", help="write the report to reports/g5/")
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code, report = run_review(write=args.write, report_dir=args.report_dir)
    if args.json:
        _print_json(report)
    else:
        _print_summary(exit_code, report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
