from pydantic import BaseModel, Field, NonNegativeInt


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
