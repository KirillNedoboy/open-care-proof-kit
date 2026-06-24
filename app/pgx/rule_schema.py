from pydantic import BaseModel, Field


class PgxFinding(BaseModel):
    rule_id: str = Field(min_length=1)
    drug: str = Field(min_length=1)
    gene: str = Field(min_length=1)
    variant_rsid: str = Field(min_length=1)
    genotype: str = Field(min_length=1)
    evidence_level: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    clinician_review_required: bool = True
    clinical_action_allowed: bool = False
