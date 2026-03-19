from typing import TypedDict
from uuid import UUID


class QdrantVectorMetadata(TypedDict):
    id: UUID
    title: str
    content: str
    attachments: dict[str, str] | None
    url: str | None
