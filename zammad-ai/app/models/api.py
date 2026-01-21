from pydantic import BaseModel

from app.models.triage import TriageResult


class TriageInput(BaseModel):
    text: str
    id: str | None = None


class TriageReturn(BaseModel):
    triage: TriageResult
    id: str


class AnswerInput(BaseModel):
    text: str
    id: str | None = None
    category: str | None = None
