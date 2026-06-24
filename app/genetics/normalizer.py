from pydantic import BaseModel, Field


class NormalizedVariant(BaseModel):
    rsid: str | None = None
    chromosome: str = Field(min_length=1)
    position: int = Field(gt=0)
    genotype: str = Field(min_length=1)
    source: str = Field(default="unknown")
    genome_build: str | None = None
    no_call: bool = False

    @property
    def variant_key(self) -> str:
        if self.rsid:
            return self.rsid
        return f"{self.chromosome}:{self.position}:{self.genotype}"
