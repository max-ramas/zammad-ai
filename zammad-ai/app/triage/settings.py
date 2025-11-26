import operator as op
import os
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

load_dotenv()

PATH_TO_YAML_CONFIG = os.getenv("PATH_TO_YAML_CONFIG", "")


class Usecase(BaseModel):
    name: str
    description: str


class Category(BaseModel):
    name: str
    description: str
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


def get_operator_function(operator: ConditionOperator):
    """Map ConditionOperator enum to Python operator functions."""
    operator_map = {
        ConditionOperator.EQUALS: op.eq,
        ConditionOperator.NOT_EQUALS: op.ne,
        ConditionOperator.LESS: op.lt,
        ConditionOperator.LESS_EQUALS: op.le,
        ConditionOperator.GREATER: op.gt,
        ConditionOperator.GREATER_EQUALS: op.ge,
    }
    return operator_map.get(operator, op.eq)


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


class PromptConfig(BaseModel):
    categories_prompt: str = "kategorien.md"
    edge_cases_prompt: str = "edge_cases.md"
    examples_prompt: str = "examples.md"
    role_prompt: str = "role.md"


class ZammadAISettings(BaseSettings):
    usecase: Usecase
    categories: list[Category]
    no_category: Category
    actions: list[Action]
    no_action: Action
    action_rules: list[ActionRule]
    prompt_config: PromptConfig

    model_config = SettingsConfigDict(yaml_file=PATH_TO_YAML_CONFIG, env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=PATH_TO_YAML_CONFIG),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
