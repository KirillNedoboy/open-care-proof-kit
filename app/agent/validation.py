import re

from app.agent.models import AgentAnswer, AgentContext


class ValidationResult:
    def __init__(self, valid: bool, reason_code: str | None = None) -> None:
        self.valid = valid
        self.reason_code = reason_code


UNSAFE_PRESCRIPTIVE_PATTERNS = (
    r"\byou should (take|start|stop|increase|decrease|change|switch)\b",
    r"\b(increase|decrease|adjust) (your |the )?(dose|dosage)\b",
    r"\bstart taking\b|\bstop taking\b|\bdiscontinue\b",
    r"\byou have (a |an )?(diagnosis|condition)\b",
    r"\bi recommend\b|\bthe best treatment\b",
)
PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\|/(?:home|tmp|var|Users|private)/)")
SECRET_PATTERN = re.compile(r"(?:api[_ -]?key|authorization|bearer\s+[A-Za-z0-9])", re.IGNORECASE)


def validate_answer(answer: AgentAnswer, context: AgentContext) -> ValidationResult:
    known_source_ids = {source.source_id for source in context.sources}
    if any(citation.source_id not in known_source_ids for citation in answer.citations):
        return ValidationResult(False, "unknown_citation")
    content = "\n".join(
        [answer.answer, *answer.unknowns, *answer.doctor_questions, *answer.boundary_notices]
    )
    if PATH_PATTERN.search(content):
        return ValidationResult(False, "private_path")
    if SECRET_PATTERN.search(content):
        return ValidationResult(False, "secret_pattern")
    if any(
        re.search(pattern, content, flags=re.IGNORECASE)
        for pattern in UNSAFE_PRESCRIPTIVE_PATTERNS
    ):
        return ValidationResult(False, "unsafe_prescriptive_claim")
    return ValidationResult(True)
