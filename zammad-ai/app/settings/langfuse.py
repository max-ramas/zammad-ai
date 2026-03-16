from pydantic import BaseModel, Field


class LangfusePrompt(BaseModel):
    label: str = Field(
        description="Label of the prompt in Langfuse",
        default="production",
    )
    name: str = Field(
        description="Name of the prompt in Langfuse",
        examples=["use_case/triage/prompt_name"],
    )
