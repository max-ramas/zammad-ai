from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, FilePath, HttpUrl, PositiveInt

from app.utils.validators import validate_is_prompt

from .langfuse import LangfusePrompt


class StringAnswerPrompt(BaseModel):
    """Prompt configuration for answer generation using a raw string template."""

    type: Literal["string"] = "string"
    prompt: str = Field(
        description="The prompt template for answer generation as a raw string.",
        default="",
    )


class FileAnswerPrompt(BaseModel):
    """Prompt configuration for answer generation using a file path."""

    type: Literal["file"] = "file"
    prompt: Annotated[FilePath, AfterValidator(func=validate_is_prompt)] = Field(
        description="The file path to the prompt template for answer generation.",
    )


class LangfuseAnswerPrompt(BaseModel):
    """Prompt configuration for answer generation using a Langfuse prompt reference."""

    type: Literal["langfuse"] = "langfuse"
    prompt: LangfusePrompt = Field(
        description="The name and label of the Langfuse prompt to use for answer generation.",
    )


AnswerPrompt = Annotated[
    StringAnswerPrompt | FileAnswerPrompt | LangfuseAnswerPrompt,
    Field(discriminator="type"),
]


class AnswerSettings(BaseModel):
    agent_prompt: StringAnswerPrompt | FileAnswerPrompt | LangfuseAnswerPrompt = Field(
        description="Prompt configuration for the answer generation agent. Can be provided as a raw string, a file path, or a Langfuse prompt reference.",
        default=FileAnswerPrompt(
            prompt=Path("prompts/answer/agent.prompt.md"),
        ),
    )
    dlf: DLFSettings | None = Field(
        default=None,
    )


class DLFSettings(BaseModel):
    """Settings for the Dienstleistungsfinder (DLF) integration."""

    url: HttpUrl = Field(
        description="The base URL of the DLF API.",
    )
    filter_categories: list[str] = Field(
        description="List of categories to filter DLF results. If empty, no category filtering will be applied.",
        default_factory=list,
    )
    timeout: PositiveInt = Field(
        description="Timeout in seconds for requests to the DLF API.",
        default=60,
    )
