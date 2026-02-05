from pydantic import BaseModel, Field


class Usecase(BaseModel):
    name: str
    description: str


class OpenAISettings(BaseModel):
    api_key: str = Field(description="API key for OpenAI")
    url: str = Field(description="Base URL for OpenAI API")
    completions_model: str = Field(default="gpt-4.1-mini", description="Model to use for completions")
    embeddings_model: str = Field(default="text-embedding-3-large", description="Model to use for embeddings")
    reasoning_effort: str | None = Field(default=None, description="Reasoning effort level for models that support it")
    temperature: float = Field(default=0.0, description="Temperature for LLM responses")
    max_retries: int = Field(default=5, description="Maximum retry attempts")


class LangfuseSettings(BaseModel):
    secret_key: str = Field(description="Langfuse secret key")
    public_key: str = Field(description="Langfuse public key")
    base_url: str = Field(description="Langfuse base URL")


class ZammadSettings(BaseModel):
    base_url: str = Field(description="Zammad base URL")
    auth_token: str = Field(description="Zammad API authentication token")
    knowledge_base_id: str = Field(default="1", description="Knowledge base ID")
    rss_feed_token: str = Field(default="", description="RSS feed token")


class QdrantSettings(BaseModel):
    host: str = Field(description="Qdrant server URL")
    api_key: str = Field(description="Qdrant API key")
    collection_name: str = Field(description="Qdrant collection name")
    vector_name: str = Field(default="", description="Qdrant vector name")
    vector_dimension: int = Field(default=1024, description="Dimension of the vectors stored in Qdrant")


class CoreSettings(BaseModel):
    usecase: Usecase
    openai: OpenAISettings
    langfuse: LangfuseSettings
    zammad: ZammadSettings
    qdrant: QdrantSettings
