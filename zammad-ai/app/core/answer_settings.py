from pydantic import BaseModel


class AnswerSettings(BaseModel):
    answer_agent_prompt: str = ""
