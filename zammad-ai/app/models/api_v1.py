from pydantic import BaseModel, Field

from .triage import TriageResult


class TriageInput(BaseModel):
    text: str
    id: str | None = None


class TriageOutput(BaseModel):
    triage: TriageResult
    id: str


class AnswerInput(BaseModel):
    text: str
    id: str | None = None
    category: str | None = None


class HealthCheckReponse(BaseModel):
    status: str = Field(
        description="Health status of the API. Expected value is 'healthy' when the API is operational.",
        default="healthy",
    )
