from enum import Enum

from pydantic import BaseModel


class Category(BaseModel):
    name: str
    id: int


class Action(BaseModel):
    name: str
    description: str
    id: int


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    LESS = "less"
    LESS_EQUALS = "less_equals"
    GREATER = "greater"
    GREATER_EQUALS = "greater_equals"


class ConditionField(str, Enum):
    PROCESSING_ID = "processing_id"
    DAYS_SINCE_REQUEST = "days_since_request"


class Condition(BaseModel):
    priority: int
    field: ConditionField
    operator: ConditionOperator
    value: str | bool | int
    action_id: int


class ActionRule(BaseModel):
    category_id: int
    action_id: int = 0
    conditions: list[Condition] | None = None


class ProcessingState(BaseModel):
    operator: str
    datetime: str


class LangfusePromptConfig(BaseModel):
    label: str = "latest"
    categories_prompt: str = "drivers-licence/categories"
    examples_prompt: str = "drivers-licence/examples"
    role_prompt: str = "drivers-licence/role"


class TriageSettings(BaseModel):
    categories: list[Category]
    no_category_id: int
    actions: list[Action]
    no_action_id: int
    action_rules: list[ActionRule]
    prompt_config: LangfusePromptConfig
