from pydantic import BaseModel


class DLFSettings(BaseModel):
    url: str = ""
    categories: list[str] = []
    keywords: list[str] = []


class AnswerSettings(BaseModel):
    answer_agent_prompt: str = ""
    dlf: DLFSettings = DLFSettings()
