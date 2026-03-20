from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, FilePath, field_validator


class TriageSettings(BaseModel):
    categories: list["Category"]
    no_category_name: str
    actions: list["Action"]
    no_action_name: str
    action_rules: list["ActionRule"]
    prompts: StringTriagePrompts | FileTriagePrompts | LangfuseTriagePrompts = Field(
        description="Prompts for the triage process. Can be provided as raw strings, file paths, or Langfuse prompt references.",
        discriminator="type",
    )

    @staticmethod
    def _validate_unique_names(v: list[dict | BaseModel], field_singular_name: str):
        if not v:
            raise ValueError(f"At least one {field_singular_name} must be provided")

        seen_names: set[str] = set()
        for item in v:
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if name is None:
                raise ValueError(f"Each {field_singular_name} must define a name")
            if name in seen_names:
                raise ValueError("Names must be unique")
            seen_names.add(name)
        return v

    @field_validator("actions", mode="before")
    def validate_actions_for_unique_names(cls, v):
        return cls._validate_unique_names(v, "action")

    @field_validator("categories", mode="before")
    def validate_categories_for_unique_names(cls, v):
        return cls._validate_unique_names(v, "category")


class Category(BaseModel):
    name: str
    auto_publish: bool = False


class ActionTypes(str, Enum):
    AI_Answer = "AI_Answer"
    No_Action = "No_Action"
    Standard_Answer = "Standard_Answer"


class Action(BaseModel):
    name: str
    description: str
    type: ActionTypes
    answer: str | None = None


class ActionRule(BaseModel):
    category_name: str
    action_name: str
    conditions: list["Condition"] | None = None


ConditionOperator = Literal["equals", "not_equals", "less", "less_equals", "greater", "greater_equals"]
ConditionField = Literal["processing_id", "days_since_request"]


class Condition(BaseModel):
    priority: int
    field: "ConditionField"
    operator: "ConditionOperator"
    value: str | bool | int
    action_name: str


class ProcessingState(BaseModel):
    operator: str
    datetime: str


TriagePrompt = Literal["categories", "examples", "role"]


class StringTriagePrompts(BaseModel):
    type: Literal["string"] = "string"
    prompt_map: dict[TriagePrompt, str] = Field(
        description="Prompts for the triage process as raw strings. The keys should be 'categories', 'examples', and 'role'.",
        default={
            "categories": "List of categories: {{categories}}",
            "examples": "Examples: {{examples}}",
            "role": "You are a helpful assistant that categorizes support requests into the above categories based on the content of the request.",
        },
    )


class FileTriagePrompts(BaseModel):
    type: Literal["file"] = "file"
    prompt_map: dict[TriagePrompt, FilePath] = Field(
        description="Prompts for the triage process as file paths. The files should contain the prompts as raw text. The keys should be 'categories', 'examples', and 'role'.",
    )


class LangfuseTriagePrompts(BaseModel):
    type: Literal["langfuse"] = "langfuse"
    prompt_map: dict[TriagePrompt, "LangfusePrompt"] = Field(
        description="Prompts for the triage process as LangfusePrompt objects. The keys should be 'categories', 'examples', and 'role'.",
    )


class LangfusePrompt(BaseModel):
    label: str = Field(
        description="Label of the prompt in Langfuse",
        default="production",
    )
    name: str = Field(
        description="Name of the prompt in Langfuse",
        examples=["use_case/triage/prompt_name"],
    )
