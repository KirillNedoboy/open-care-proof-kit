import json
from pathlib import Path
from types import SimpleNamespace

from app import cli


def test_demo_report_cli_writes_markdown_and_audit_files(tmp_path: Path) -> None:
    exit_code = cli.main(["demo-report", "--drug", "sertraline", "--out-dir", str(tmp_path)])

    report_path = tmp_path / "demo-sertraline-briefing.md"
    audit_path = tmp_path / "demo-sertraline-audit.json"

    assert exit_code == 0
    assert report_path.exists()
    assert audit_path.exists()
    assert "Medication-to-Doctor Briefing" in report_path.read_text(encoding="utf-8")

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["drug"] == "sertraline"
    assert audit["policy_passed"] is True
    assert audit["generated_files"] == {
        "report_markdown": str(report_path),
        "audit_json": str(audit_path),
    }


def test_demo_report_cli_returns_nonzero_when_safety_policy_fails(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    unsafe_result = SimpleNamespace(
        report_markdown="unsafe report",
        audit={"policy_passed": False},
        policy_passed=False,
        policy_violations=["dosage_recommendation"],
    )
    monkeypatch.setattr(cli, "build_demo_briefing", lambda drug: unsafe_result)

    exit_code = cli.main(["demo-report", "--drug", "sertraline", "--out-dir", str(tmp_path)])

    assert exit_code == 1
    assert not (tmp_path / "demo-sertraline-briefing.md").exists()
    assert not (tmp_path / "demo-sertraline-audit.json").exists()
