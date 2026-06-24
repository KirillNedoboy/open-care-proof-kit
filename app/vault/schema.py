from pydantic import BaseModel, Field


class Problem(BaseModel):
    name: str = Field(min_length=1)
    status: str = Field(default="active")
    notes: str = Field(default="")


class Medication(BaseModel):
    name: str = Field(min_length=1)
    status: str = Field(default="current")
    notes: str = Field(default="")


class HealthVault(BaseModel):
    patient_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    data_classification: str = Field(default="synthetic_demo_only")
    age_range: str = Field(default="adult")
    sex: str = Field(default="unspecified")
    problems: list[Problem] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    notes: str = Field(default="")

    def assert_demo_only(self) -> None:
        if self.data_classification != "synthetic_demo_only":
            raise ValueError("MVP only allows synthetic_demo_only data.")
