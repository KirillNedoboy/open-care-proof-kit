import json
from pathlib import Path
from typing import Any

from evals.metrics import EvalSummary
from evals.runner import ROOT, run_evals

DEFAULT_MANIFEST_PATH = (
    ROOT / "docs" / "assets" / "health_vault" / "family-vault-manifest.json"
)
DEFAULT_GITIGNORE_PATH = ROOT / ".gitignore"

UNAVAILABLE = "unavailable"


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def bool_label(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return UNAVAILABLE


def provenance_complete_label(manifest: dict[str, Any] | None) -> str:
    if manifest is None:
        return UNAVAILABLE
    coverage = manifest.get("provenance_coverage_summary")
    if not isinstance(coverage, dict):
        return UNAVAILABLE

    total = coverage.get("total_important_records")
    with_source = coverage.get("records_with_source")
    missing_count = coverage.get("records_missing_source")
    missing_ids = coverage.get("missing_source_item_ids")
    if not isinstance(total, int):
        return UNAVAILABLE
    if not isinstance(with_source, int):
        return UNAVAILABLE
    if not isinstance(missing_count, int):
        return UNAVAILABLE
    if not isinstance(missing_ids, list):
        return UNAVAILABLE

    complete = total == with_source and missing_count == 0 and not missing_ids
    return str(complete).lower()


def generated_reports_ignored_label(gitignore_path: Path = DEFAULT_GITIGNORE_PATH) -> str:
    if not gitignore_path.is_file():
        return UNAVAILABLE
    try:
        lines = {
            line.strip()
            for line in gitignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
    except OSError:
        return UNAVAILABLE

    ignored = "reports/*" in lines and "!reports/.gitkeep" in lines
    return str(ignored).lower()


def eval_metric_lines(summary: EvalSummary) -> list[str]:
    return [
        f"- total_cases: {summary.total_cases}",
        f"- static_text_cases: {summary.static_text_cases}",
        f"- pipeline_cases: {summary.pipeline_cases}",
        f"- passed_cases: {summary.passed_cases}",
        f"- failed_cases: {summary.failed_cases}",
        f"- unsafe_advice_rate: {summary.unsafe_advice_rate}",
        f"- missing_source_rate: {summary.missing_source_rate}",
        f"- uncertainty_missing_rate: {summary.uncertainty_missing_rate}",
        f"- audit_missing_rate: {summary.audit_missing_rate}",
        f"- pipeline_failure_rate: {summary.pipeline_failure_rate}",
    ]


def artifact_safety_lines(
    manifest: dict[str, Any] | None,
    gitignore_path: Path,
) -> list[str]:
    no_llm_generation = bool_label(
        manifest.get("no_llm_generation") if manifest else None
    )
    no_medical_advice = bool_label(
        manifest.get("no_medical_advice") if manifest else None
    )
    return [
        f"- manifest_status: {'available' if manifest is not None else UNAVAILABLE}",
        f"- demo_only: {bool_label(manifest.get('demo_only') if manifest else None)}",
        f"- synthetic: {bool_label(manifest.get('synthetic') if manifest else None)}",
        f"- no_llm_generation: {no_llm_generation}",
        f"- no_genetics: {bool_label(manifest.get('no_genetics') if manifest else None)}",
        f"- no_medical_advice: {no_medical_advice}",
        f"- provenance_complete: {provenance_complete_label(manifest)}",
        f"- generated_reports_ignored: {generated_reports_ignored_label(gitignore_path)}",
        "- health_vault_focused_tests_expected: "
        "tests/test_health_vault.py tests/test_health_vault_read_model.py "
        "tests/test_health_vault_artifacts.py",
    ]


def build_trust_metrics_report(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    gitignore_path: Path = DEFAULT_GITIGNORE_PATH,
) -> str:
    summary = run_evals()
    manifest = load_manifest(manifest_path)

    lines = [
        "# Trust Metrics",
        "",
        "Automated demo/reviewer trust checks for OpenCare Proof Kit.",
        "These checks are local and deterministic. They are not clinical validation.",
        "",
        "## Eval Metrics",
        *eval_metric_lines(summary),
        "",
        "## Health/Family Vault Artifact Safety",
        "Synthetic/demo artifact safety flags from the committed manifest:",
        *artifact_safety_lines(manifest, gitignore_path),
        "",
        "## Safety Boundary Checks",
        "- not clinical validation",
        "- not medical advice",
        "- not diagnosis",
        "- no LLM generation in the Health/Family Vault artifact layer",
        "- no genetics support in the Health/Family Vault artifact layer",
        "- generated reports under reports/ are generated artifacts and should remain ignored",
        "",
        "## Residual Risks",
        "- These automated demo/reviewer trust checks do not prove clinical correctness.",
        "- Artifact tampering is documented as a residual risk, not solved by this report.",
        "- Future user data is not safe by default without validation and provenance checks.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = build_trust_metrics_report()
    print(report, end="")


if __name__ == "__main__":
    main()
