import re

from app.safety.violations import SafetyViolation

BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("diagnosis_claim", re.compile(r"\b(diagnosed with|you have|diagnosis is)\b", re.I)),
    (
        "dosage_recommendation",
        re.compile(r"\b(\d+\s?mg|increase.*dose|reduce.*dose|change.*dose)\b", re.I),
    ),
    (
        "start_stop_instruction",
        re.compile(r"\b(you should start|you should stop|stop taking|start taking)\b", re.I),
    ),
)

REQUIRED_PHRASES: tuple[tuple[str, str], ...] = (
    ("missing_safety_note", "not medical advice"),
    ("missing_clinician_review", "clinician"),
    ("missing_sources", "sources"),
    ("missing_limitations", "limitations"),
    ("missing_audit", "audit"),
)


def evaluate_report_safety(report: str) -> list[SafetyViolation]:
    violations: list[SafetyViolation] = []

    for code, pattern in BLOCK_PATTERNS:
        if pattern.search(report):
            violations.append(
                SafetyViolation(code=code, message=f"Blocked unsafe phrase pattern: {code}")
            )

    lowered = report.lower()
    for code, required_phrase in REQUIRED_PHRASES:
        if required_phrase not in lowered:
            violations.append(
                SafetyViolation(
                    code=code,
                    message=f"Required report phrase missing: {required_phrase}",
                )
            )

    return violations
