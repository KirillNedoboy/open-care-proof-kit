from app.demo_pipeline import PIPELINE_STEPS, build_demo_briefing


def test_build_demo_briefing_returns_safe_result() -> None:
    result = build_demo_briefing("sertraline")

    assert result.policy_passed is True
    assert result.policy_violations == []
    assert result.findings_count == 1
    assert "Medication-to-Doctor Briefing" in result.report_markdown
    assert result.audit["drug"] == "sertraline"
    assert result.audit["findings_count"] == 1
    assert result.audit["report_id"]
    assert result.audit["app_version"] == "0.1.0"
    assert result.audit["pipeline_steps"] == PIPELINE_STEPS
    assert result.audit["raw_health_or_genetic_data_exported"] is False
    assert "patient_id" not in result.audit
