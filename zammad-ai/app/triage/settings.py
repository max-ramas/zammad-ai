import operator as op
import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

load_dotenv()

PATH_TO_YAML_CONFIG = os.getenv("PATH_TO_YAML_CONFIG", "")


class Usecase(BaseModel):
    name: str
    description: str


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


def id_to_category(category_id: int) -> Category:
    for category in ZammadAISettings().categories:  # type: ignore
        if category.id == category_id:
            return category
    no_category = next((c for c in ZammadAISettings().categories if c.id == ZammadAISettings().no_category_id), None)  # type: ignore
    return no_category if no_category else Category(id=-1, name="no_category")


def id_to_action(action_id: int) -> Action:
    for action in ZammadAISettings().actions:  # type: ignore
        if action.id == action_id:
            return action
    no_action = next((a for a in ZammadAISettings().actions if a.id == ZammadAISettings().no_action_id), None)  # type: ignore
    return no_action if no_action else Action(id=-1, name="no_action", description="No action")


class UTF8YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom YAML config source that explicitly uses UTF-8 encoding."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_file: str | Path | None):
        super().__init__(settings_cls)
        self.yaml_file = yaml_file

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        # Not used for this source
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not self.yaml_file:
            return {}

        yaml_path = Path(self.yaml_file)
        if not yaml_path.exists():
            return {}

        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


class ZammadAISettings(BaseSettings):
    usecase: Usecase
    categories: list[Category]
    no_category_id: int
    actions: list[Action]
    no_action_id: int
    action_rules: list[ActionRule]
    prompt_config: PromptConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

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
            UTF8YamlConfigSettingsSource(settings_cls, yaml_file=PATH_TO_YAML_CONFIG),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
