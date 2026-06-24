from pydantic import BaseModel, Field


class SafetyViolation(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
