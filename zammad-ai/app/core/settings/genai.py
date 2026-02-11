from typing import Literal

from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt


class GenAISettings(BaseModel):
    """
    Settings for GenAI integration, including model selection and configuration.
    API keys and URLs are expected to be provided via environment variables or other secure means.
    """

    sdk: Literal["openai"] = Field(
        description="GenAI SDK to use",
        default="openai",
    )
    chat_model: str = Field(
        default="gpt-4.1-mini",
        description="Model to use for completions",
    )
    embeddings_model: str = Field(
        description="Model to use for embeddings",
        default="text-embedding-3-large",
    )
    reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = Field(
        description="Reasoning effort for supporting models",
        default=None,
    )
    temperature: NonNegativeFloat = Field(
        description="Temperature for LLM responses (0.0 to 2.0)",
        default=0.0,
        le=2.0,
    )
    max_retries: NonNegativeInt = Field(
        description="Maximum retry attempts",
        default=3,
    )

    @property
    def store(self) -> bool | None:
        """Determines whether to store interactions based on the configured GenAI SDK."""
        if self.reasoning_effort is not None:
            return False
        return None

    @property
    def reasoning_config(self) -> dict[str, str] | None:
        """Constructs a reasoning configuration dictionary for LLM interactions based on the configured reasoning effort."""
        if self.reasoning_effort is not None:
            return {
                "reasoning_effort": self.reasoning_effort,
                "summary": "detailed",
            }
        return None
