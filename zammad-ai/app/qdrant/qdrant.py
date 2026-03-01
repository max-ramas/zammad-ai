from logging import Logger
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from langchain.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import ApiException
from qdrant_client.http.models import CollectionInfo
from qdrant_client.models import SnapshotDescription

from app.settings import GenAISettings, QdrantSettings
from app.utils.logging import getLogger

# Create a consistent namespace UUID for generating vector IDs based on content
ZAMMAD_AI_NAMESPACE: UUID = uuid5(
    namespace=NAMESPACE_DNS,
    name="zammad-ai.muenchen.de",
)
RETRIEVAL_NUM_DOCUMENTS = 5  # TODO: Move magic number to config or even better to agent


class QdrantKBError(Exception):
    """Custom exception for Qdrant-related errors."""

    ...


class QdrantKBClient:
    """Wrapper around Qdrant client to handle vector storage and retrieval."""

    def __init__(self, qdrant_settings: QdrantSettings, genai_settings: GenAISettings) -> None:
        # Create logger for QdrantClient
        self.logger: Logger = getLogger("zammad-ai.qdrant")

        self.collection_name: str = qdrant_settings.collection_name

        # Create sync + async Qdrant client with appropriate configuration
        self.client = QdrantClient(
            url=qdrant_settings.url.encoded_string(),
            port=None,  # Port is included in the URL, so we set it to None
            timeout=qdrant_settings.timeout,
            api_key=qdrant_settings.api_key.get_secret_value() if qdrant_settings.api_key else None,
        )
        self.aclient = AsyncQdrantClient(
            url=qdrant_settings.url.encoded_string(),
            port=None,  # Port is included in the URL, so we set it to None
            timeout=qdrant_settings.timeout,
            api_key=qdrant_settings.api_key.get_secret_value() if qdrant_settings.api_key else None,
        )

        # Check if collection exists and if there is data in it, else raise an Error
        try:
            if not self.client.collection_exists(collection_name=qdrant_settings.collection_name):
                self.logger.error(f"Qdrant collection '{qdrant_settings.collection_name}' does not exist.")
                raise QdrantKBError(f"Qdrant collection '{qdrant_settings.collection_name}' does not exist.")

            collection_info: CollectionInfo = self.client.get_collection(collection_name=qdrant_settings.collection_name)
            if collection_info.points_count == 0:
                self.logger.warning(f"Qdrant collection '{qdrant_settings.collection_name}' exists but is empty.")
                raise QdrantKBError(f"Qdrant collection '{qdrant_settings.collection_name}' exists but is empty.")

        except ApiException as e:
            self.logger.error("Error checking Qdrant collection existence or retrieving collection info", exc_info=True)
            raise QdrantKBError("Failed to check Qdrant collection existence or retrieve collection info") from e

        # Create LangChain embedding model
        self.embeddings: Embeddings

        match genai_settings.sdk:
            case "openai":
                from langchain_openai import OpenAIEmbeddings

                self.embeddings = OpenAIEmbeddings(
                    model=genai_settings.embedding_model,
                    dimensions=qdrant_settings.vector_dimension,
                    max_retries=genai_settings.max_retries,
                )
            case _:
                self.logger.error(f"Unsupported GenAI SDK '{genai_settings.sdk}' for embeddings")
                raise QdrantKBError(f"Unsupported GenAI SDK '{genai_settings.sdk}' for embeddings")

        # Test embedding to ensure configuration is correct
        test_result: list[float] = self.embeddings.embed_query("This is a test string")
        if len(test_result) != qdrant_settings.vector_dimension:
            self.logger.error(
                f"Embedding dimension mismatch: expected {qdrant_settings.vector_dimension}, got {len(test_result)}. Check your GenAI embedding model configuration."
            )
            raise QdrantKBError(
                f"Embedding dimension mismatch: expected {qdrant_settings.vector_dimension}, got {len(test_result)}. Check your GenAI embedding model configuration."
            )

        # Create LangChain Qdrant vector store
        self.vectorstore = QdrantVectorStore(
            client=self.client,
            collection_name=qdrant_settings.collection_name,
            embedding=self.embeddings,
            vector_name="dense" if qdrant_settings.vector_name is None else qdrant_settings.vector_name,
        )

        self.retriever: VectorStoreRetriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": RETRIEVAL_NUM_DOCUMENTS},
        )

    async def acreate_snapshot(self) -> bool:
        """Create a snapshot of the Qdrant collection for backup purposes.

        Returns:
            bool: True if snapshot creation was successful, False otherwise.
        """
        snapshot_description: SnapshotDescription | None = await self.aclient.create_snapshot(
            collection_name=self.collection_name, wait=True
        )
        return snapshot_description is None

    def create_snapshot(self) -> bool:
        """Create a snapshot of the Qdrant collection for backup purposes.

        Returns:
            bool: True if snapshot creation was successful, False otherwise.
        """
        snapshot_description: SnapshotDescription | None = self.client.create_snapshot(collection_name=self.collection_name, wait=True)
        return snapshot_description is None

    async def asearch_documents(
        self,
        query: str,
        k: int = RETRIEVAL_NUM_DOCUMENTS,
        offset: int = 0,
    ) -> list[tuple[Document, float]]:
        """Search for relevant documents in the Qdrant collection based on a query string.

        Args:
            query (str): The query string to search for relevant documents.
            k (int, optional): The number of top relevant documents to return. Defaults to RETRIEVAL_NUM_DOCUMENTS.
            offset (int, optional): The number of top relevant documents to skip for pagination. Defaults to 0.

        Returns:
            list[tuple[Document, float]]: A list of tuples containing relevant documents and their corresponding relevance scores between 0 and 1.
        """
        return await self.vectorstore.asimilarity_search_with_relevance_scores(
            query=query,
            k=k,
            offset=offset,
        )

    def search_documents(
        self,
        query: str,
        k: int = RETRIEVAL_NUM_DOCUMENTS,
        offset: int = 0,
    ) -> list[tuple[Document, float]]:
        """Search for relevant documents in the Qdrant collection based on a query string.

        Args:
            query (str): The query string to search for relevant documents.
            k (int, optional): The number of top relevant documents to return. Defaults to RETRIEVAL_NUM_DOCUMENTS.
            offset (int, optional): The number of top relevant documents to skip for pagination. Defaults to 0.

        Returns:
            list[tuple[Document, float]]: A list of tuples containing relevant documents and their corresponding relevance scores between 0 and 1.
        """
        return self.vectorstore.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            offset=offset,
        )

    async def aadd_document(self, content: str, metadata: dict[str, Any], id: str | None = None) -> None:
        """Add a document to the Qdrant collection with the given content, metadata, and optional ID.

        Args:
            content (str): The textual content of the document to be added.
            metadata (dict[str, Any]): A dictionary containing metadata associated with the document.
            id (str | None, optional): An optional unique identifier for the document. If not provided, a UUID will be generated based on the content. Defaults to None.

        Returns:
            None
        """
        vector_id: str = id if id is not None else str(uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=content))
        document = Document(page_content=content, metadata=metadata)
        await self.vectorstore.aadd_documents(documents=[document], ids=[vector_id])

    def add_document(self, content: str, metadata: dict[str, Any], id: str | None = None) -> None:
        """Add a document to the Qdrant collection with the given content, metadata, and optional ID.

        Args:
            content (str): The textual content of the document to be added.
            metadata (dict[str, Any]): A dictionary containing metadata associated with the document.
            id (str | None, optional): An optional unique identifier for the document. If not provided, a UUID will be generated based on the content. Defaults to None.

        Returns:
            None
        """
        vector_id: str = id if id is not None else str(uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=content))
        document = Document(page_content=content, metadata=metadata)
        self.vectorstore.add_documents(documents=[document], ids=[vector_id])
