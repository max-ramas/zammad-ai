from pydantic import BaseModel, Field


class FrontendSettings(BaseModel):
    """
    Settings for the optional frontend."
    """

    enabled: bool = Field(
        description="Whether to enable the optional frontend for Zammad AI.",
        default=False,
    )
