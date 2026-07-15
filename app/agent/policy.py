import re

from app.agent.models import PolicyDecision

URGENT_PATTERNS = (
    r"chest pain",
    r"cannot breathe|can.t breathe|difficulty breathing",
    r"overdose",
    r"suicid|self[- ]harm",
    r"immediate danger|emergency",
)
BLOCKED_PATTERNS = (
    r"what diagnosis do i have|diagnose me|do i have .*diagnos",
    r"which medication should i choose|should i take .*medication|recommend .*medication",
    r"increase (my |the )?(dose|dosage)|decrease (my |the )?(dose|dosage)",
    r"should i stop taking|should i start taking|change (my |the )?medication",
    r"what treatment should i start|recommend .*treatment",
    r"genetic variant|genotype|pgx|pharmacogen|dna result",
)


def classify_question(question: str) -> PolicyDecision:
    normalized = " ".join(question.lower().split())
    if any(re.search(pattern, normalized) for pattern in URGENT_PATTERNS):
        return PolicyDecision(
            decision="urgent",
            reason_code="urgent_language",
            response_text=(
                "If you may be in immediate danger, contact local emergency services or a "
                "licensed medical professional now. OpenCare cannot assess emergencies."
            ),
        )
    if any(re.search(pattern, normalized) for pattern in BLOCKED_PATTERNS):
        return PolicyDecision(
            decision="blocked",
            reason_code="clinical_or_genetics_request",
            response_text=(
                "OpenCare can summarize recorded, source-backed vault information but cannot "
                "diagnose, recommend treatment, select medication, or advise medication changes."
            ),
        )
    return PolicyDecision(decision="allowed", reason_code="recorded_context", response_text="")
