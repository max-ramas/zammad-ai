"""Settings and prompt models for triage classification."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, FilePath, NonNegativeInt

from app.utils.validators import validate_is_prompt

from .langfuse import LangfusePrompt


class TriageSettings(BaseModel):
    """Settings for triage categories, actions, rules, and prompts."""

    categories: list["Category"]
    no_category_id: int
    actions: list["Action"]
    no_action_id: int
    action_rules: list["ActionRule"]
    prompts: "StringTriagePrompts | FileTriagePrompts | LangfuseTriagePrompts" = Field(
        description="Prompts for the triage process. Can be provided as raw strings, file paths, or Langfuse prompt references.",
        default_factory=lambda: StringTriagePrompts(
            categories="Categorize the following text into one of the following categories: {categories}.",
            examples="Here are some examples of texts and their corresponding categories: {examples}.",
            role="You are a helpful assistant that categorizes text based on the provided categories and examples.",
        ),
        discriminator="type",
    )


class Category(BaseModel):
    """A triage category with a display name and identifier."""

    name: str
    id: int


class Action(BaseModel):
    """Action metadata associated with a triage result."""

    name: str
    description: str
    id: NonNegativeInt


class ActionRule(BaseModel):
    """Rule that maps a category to an action and optional conditions."""

    category_id: int
    action_id: NonNegativeInt
    conditions: list["Condition"] | None = None


ConditionOperator = Literal["equals", "not_equals", "less", "less_equals", "greater", "greater_equals"]
ConditionField = Literal["processing_id", "days_since_request"]


class Condition(BaseModel):
    """Condition used to select a triage action."""

    priority: int
    field: "ConditionField"
    operator: "ConditionOperator"
    value: str | bool | int
    action_id: int


class ProcessingState(BaseModel):
    """Stored state used while evaluating processing-id rules."""

    operator: str
    datetime: str


TriagePrompt = Literal["categories", "examples", "role"]


class StringTriagePrompts(BaseModel):
    """Triage prompt templates provided as raw strings."""

    type: Literal["string"] = "string"
    categories: str = Field(
        description="Prompt for categorizing text.",
    )
    examples: str = Field(
        description="Prompt with examples of categorization.",
    )
    role: str = Field(
        description="Role/system prompt for the text categorization assistant.",
    )


class FileTriagePrompts(BaseModel):
    """Triage prompt templates loaded from files."""

    type: Literal["file"] = "file"
    categories: Annotated[FilePath, AfterValidator(func=validate_is_prompt)] = Field(
        description="Path to file containing the categorization prompt.",
    )
    examples: Annotated[FilePath, AfterValidator(func=validate_is_prompt)] = Field(
        description="Path to file containing the examples prompt.",
    )
    role: Annotated[FilePath, AfterValidator(func=validate_is_prompt)] = Field(
        description="Path to file containing the role/system prompt.",
    )


class LangfuseTriagePrompts(BaseModel):
    """Triage prompt references loaded from Langfuse."""

    type: Literal["langfuse"] = "langfuse"
    categories: LangfusePrompt = Field(
        description="Langfuse prompt reference for categorizing text.",
    )
    examples: LangfusePrompt = Field(
        description="Langfuse prompt reference with examples of categorization.",
    )
    role: LangfusePrompt = Field(
        description="Langfuse prompt reference for the role/system prompt.",
    )
