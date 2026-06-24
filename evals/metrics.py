from pydantic import BaseModel


class EvalResult(BaseModel):
    case_id: str
    passed: bool
    failures: list[str]


class EvalSummary(BaseModel):
    passed_cases: int
    failed_cases: int
    unsafe_advice_rate: float
    missing_source_rate: float
    uncertainty_missing_rate: float
    audit_missing_rate: float
    results: list[EvalResult]
