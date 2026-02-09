from pydantic import BaseModel, Field, HttpUrl, PositiveInt, SecretStr


class QdrantSettings(BaseModel):
    """
    Settings for Qdrant vector database integration, including host URL, API key, collection name, and vector configuration.
    """

    host: HttpUrl = Field(
        description="Qdrant host URL",
        examples=["https://my-qdrant.example.com"],
    )
    api_key: SecretStr = Field(
        description="Qdrant API key",
        examples=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
    )
    collection_name: str = Field(
        description="Qdrant collection name",
        examples=["my_zammad_ai_collection"],
    )
    vector_name: str | None = Field(
        description="Qdrant vector name (used for namespacing vectors, optional)",
        default=None,
    )
    vector_dimension: PositiveInt = Field(
        description="Dimension of the embeddings stored in Qdrant",
        default=1024,
    )
