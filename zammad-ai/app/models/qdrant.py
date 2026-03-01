from typing import TypedDict


class QdrantVectorMetadata(TypedDict):
    id: str
    title: str
    content: str
    attachments: dict[str, str] | None
    url: str | None
