from app.safety.policy import evaluate_report_safety


def test_safety_policy_accepts_required_safe_report() -> None:
    report = """
    This report is not medical advice.
    A clinician should review it.
    Sources are included.
    Limitations are included.
    Audit metadata is included.
    """
    assert evaluate_report_safety(report) == []


def test_safety_policy_blocks_start_stop_instruction() -> None:
    report = """
    This report is not medical advice.
    A clinician should review it.
    Sources are included.
    Limitations are included.
    Audit metadata is included.
    You should stop taking the medication.
    """
    violations = evaluate_report_safety(report)
    assert any(v.code == "start_stop_instruction" for v in violations)
