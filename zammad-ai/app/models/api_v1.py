from pydantic import BaseModel, Field

from .triage import TriageResult


class TriageInput(BaseModel):
    text: str
    session_id: str | None = None


class TriageOutput(BaseModel):
    triage: TriageResult
    session_id: str


class AnswerInput(BaseModel):
    text: str
    session_id: str | None = None
    category: str | None = None


class HealthCheckResponse(BaseModel):
    status: str = Field(
        description="Health status of the API. Expected value is 'healthy' when the API is operational.",
        default="healthy",
    )
