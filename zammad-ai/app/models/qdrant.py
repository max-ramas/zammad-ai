from pydantic import BaseModel


class QdrantVectorMetadata(BaseModel):
    id: str
    title: str
    content: str
    attachments: dict[str, str] | None = None
