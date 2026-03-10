from uuid import UUID

from pydantic import BaseModel
from src.models.zammad import KnowledgeBaseAnswer


class QdrantVectorMetadata(BaseModel):
    id: UUID
    answer_info: KnowledgeBaseAnswer
    url: str | None
