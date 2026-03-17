from pydantic import BaseModel, Field, NonNegativeInt, field_validator


class IndexJobSettings(BaseModel):
    """
    Settings for the indexing job, including configuration for fetching and processing knowledge base answers.
    """

    full_indexing: bool = Field(
        description="Whether to perform a full indexing of all knowledge base answers. If False, only answers updated within the specified interval will be indexed.",
        default=False,
    )
    interval: NonNegativeInt = Field(
        description="Interval in days to look back for updated answers when fetching from Zammad.",
        default=7,
    )
    batch_size: NonNegativeInt = Field(
        description="Number of documents to process in each batch when adding to Qdrant.",
        default=50,
    )

    @field_validator("interval", "batch_size", mode="before")
    def validate_non_negative(cls, value, field):
        if value < 0:
            raise ValueError(f"{field.name} must be a non-negative and non-zero integer")
        return value
