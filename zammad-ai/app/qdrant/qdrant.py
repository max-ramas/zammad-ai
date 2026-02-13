from uuid import NAMESPACE_DNS, UUID, uuid5

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from truststore import inject_into_ssl

from app.models.qdrant import QdrantVectorMetadata
from app.settings import ZammadAISettings, get_settings

load_dotenv()
inject_into_ssl()

NAMESPACE: UUID = uuid5(NAMESPACE_DNS, "zammad-ai")
settings: ZammadAISettings = get_settings()

embedding = OpenAIEmbeddings(
    model=settings.genai.embeddings_model,
    dimensions=settings.qdrant.vector_dimension,
)
aqdrant_client = AsyncQdrantClient(
    settings.qdrant.host.encoded_string(), api_key=settings.qdrant.api_key.get_secret_value(), port=None, timeout=60
)
qdrant_client = QdrantClient(
    settings.qdrant.host.encoded_string(), api_key=settings.qdrant.api_key.get_secret_value(), port=None, timeout=60
)
vectorstore = QdrantVectorStore(
    client=qdrant_client,
    collection_name=settings.qdrant.collection_name,
    embedding=embedding,
    vector_name=settings.qdrant.vector_name if settings.qdrant.vector_name else "",
)


async def create_snapshot() -> None:
    """Create a snapshot of the Qdrant collection."""
    await aqdrant_client.create_snapshot(collection_name=settings.qdrant.collection_name)


async def save_to_qdrant(page_content: str, metadata: QdrantVectorMetadata, id: str) -> None:
    id = str(uuid5(NAMESPACE, id))
    doc: Document = Document(page_content=page_content, metadata=metadata.model_dump(), id=id)
    await vectorstore.aadd_documents([doc], ids=[id])


async def get_similar_vectors(query: str, k: int = 5) -> list[Document]:
    """Retrieve similar vectors from Qdrant based on the query."""
    docs: list[Document] = await vectorstore.asimilarity_search(query, k=k)
    return docs


def restore_knowledge_base() -> None:
    """Restore the knowledge base from the Qdrant collection."""
    offset = 0
    limit = 100
    while True:
        result = qdrant_client.scroll(
            collection_name=settings.qdrant.collection_name,
            offset=offset,
            limit=limit,
            with_payload=True,
            with_vector=False,
        )

        points = result[0]
        offset = result[1]
        if not points:
            break
        for point in points:
            pass
            # Process the metadata and vector_id as needed to restore the knowledge base
        if offset is None:
            break
