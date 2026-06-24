from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceRule(BaseModel):
    rule_id: str = Field(min_length=1)
    drug: str = Field(min_length=1)
    gene: str = Field(min_length=1)
    variant_rsid: str = Field(min_length=1)
    matching_genotypes: list[str] = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: HttpUrl
    evidence_level: str = Field(min_length=1)
    clinical_action_allowed: bool = False
    clinician_review_required: bool = True
    summary: str = Field(min_length=1)
    limitations: str = Field(min_length=1)

    @field_validator("clinical_action_allowed")
    @classmethod
    def no_clinical_action_in_v01(cls, value: bool) -> bool:
        if value:
            raise ValueError("v0.1 does not allow clinical action rules.")
        return value


class EvidencePack(BaseModel):
    pack_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    demo_only: bool = True
    rules: list[EvidenceRule] = Field(default_factory=list)

    def assert_demo_pack(self) -> None:
        if not self.demo_only:
            raise ValueError("Only demo evidence packs are allowed in v0.1.")
