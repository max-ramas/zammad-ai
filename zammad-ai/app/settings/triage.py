from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, FilePath, NonNegativeInt

from app.utils.validators import validate_is_prompt

from .langfuse import LangfusePrompt


class TriageSettings(BaseModel):
    categories: list["Category"]
    no_category_id: int
    actions: list["Action"]
    no_action_id: int
    action_rules: list["ActionRule"]
    prompts: "StringTriagePrompts | FileTriagePrompts | LangfuseTriagePrompts" = Field(
        description="Prompts for the triage process. Can be provided as raw strings, file paths, or Langfuse prompt references.",
        default_factory=lambda: StringTriagePrompts(
            prompt_map={
                "categories": "Categorize the following text into one of the following categories: {categories}.",
                "examples": "Here are some examples of texts and their corresponding categories: {examples}.",
                "role": "You are a helpful assistant that categorizes text based on the provided categories and examples.",
            }
        ),
        discriminator="type",
    )


class Category(BaseModel):
    name: str
    id: int


class Action(BaseModel):
    name: str
    description: str
    id: NonNegativeInt


class ActionRule(BaseModel):
    category_id: int
    action_id: NonNegativeInt
    conditions: list["Condition"] | None = None


ConditionOperator = Literal["equals", "not_equals", "less", "less_equals", "greater", "greater_equals"]
ConditionField = Literal["processing_id", "days_since_request"]


class Condition(BaseModel):
    priority: int
    field: "ConditionField"
    operator: "ConditionOperator"
    value: str | bool | int
    action_id: int


class ProcessingState(BaseModel):
    operator: str
    datetime: str


TriagePrompt = Literal["categories", "examples", "role"]


class StringTriagePrompts(BaseModel):
    type: Literal["string"] = "string"
    prompt_map: dict[TriagePrompt, str] = Field(
        description="Prompts for the triage process as raw strings. The keys should be 'categories', 'examples', and 'role'.",
    )


class FileTriagePrompts(BaseModel):
    type: Literal["file"] = "file"
    prompt_map: dict[TriagePrompt, Annotated[FilePath, AfterValidator(func=validate_is_prompt)]] = Field(
        description="Prompts for the triage process as file paths. The files should contain the prompts as raw text. The keys should be 'categories', 'examples', and 'role'.",
    )


class LangfuseTriagePromptMap(BaseModel):
    categories: LangfusePrompt
    examples: LangfusePrompt
    role: LangfusePrompt


class LangfuseTriagePrompts(BaseModel):
    type: Literal["langfuse"] = "langfuse"
    prompt_map: LangfuseTriagePromptMap = Field(
        description="Prompts for the triage process as LangfusePrompt objects. The keys should be 'categories', 'examples', and 'role'.",
    )
