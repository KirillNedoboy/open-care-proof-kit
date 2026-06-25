from pydantic import BaseModel, Field, field_validator, model_validator

from app.evidence.sources import validate_source_url


class EvidenceRule(BaseModel):
    rule_id: str = Field(min_length=1)
    drug: str = Field(min_length=1)
    gene: str = Field(min_length=1)
    variant_rsid: str = Field(min_length=1)
    matching_genotypes: list[str] = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    evidence_level: str = Field(min_length=1)
    clinical_action_allowed: bool = False
    clinician_review_required: bool = True
    summary: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    demo_only: bool | None = None

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str) -> str:
        return validate_source_url(value)

    @field_validator("limitations")
    @classmethod
    def limitations_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("limitations are required.")
        return normalized

    @field_validator("clinical_action_allowed")
    @classmethod
    def no_clinical_action_in_v01(cls, value: bool) -> bool:
        if value:
            raise ValueError("clinical_action_allowed=true is not allowed in v0.1.")
        return value

    @field_validator("clinician_review_required")
    @classmethod
    def clinician_review_must_remain_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError("clinician_review_required must remain true in v0.1.")
        return value


class EvidencePack(BaseModel):
    pack_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    demo_only: bool = True
    rules: list[EvidenceRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def apply_demo_only_to_rules(self) -> "EvidencePack":
        for rule in self.rules:
            if rule.demo_only is None:
                rule.demo_only = self.demo_only
            if not rule.demo_only:
                raise ValueError("Evidence rules must be demo_only in v0.1.")
        return self

    def assert_demo_pack(self) -> None:
        if not self.demo_only:
            raise ValueError("Only demo evidence packs are allowed in v0.1.")
