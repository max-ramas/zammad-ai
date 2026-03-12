from logging import Logger
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from langchain.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import ApiException
from qdrant_client.http.models import CollectionInfo
from qdrant_client.http.models.models import Record
from qdrant_client.models import SnapshotDescription
from src.settings.genai import GenAISettings
from src.settings.qdrant import QdrantSettings
from src.utils.logging import getLogger

# Create a consistent namespace UUID for generating vector IDs based on content
ZAMMAD_AI_NAMESPACE: UUID = uuid5(
    namespace=NAMESPACE_DNS,
    name="zammad-ai.muenchen.de",
)


class SearchQdrantKBInput(BaseModel):
    query: str = Field(
        description="The search query string; should be concise and focused on the information needed; maximum length is 200 characters (~ 20 words).",
        max_length=200,
    )
    num_documents: PositiveInt = Field(
        default=5,
        description="The number of relevant documents to retrieve; should be a positive integer; default is 5.",
    )
    offset: NonNegativeInt = Field(
        default=0,
        description="The number of top relevant documents to skip for pagination; should be a non-negative integer; default is 0. Good for retrieving the next set of results in subsequent calls with the same query.",
    )


class RetrieveDocumentsKBOutput(BaseModel):
    documents_with_relevance_score: list[tuple[Document, float]] = Field(
        description="A list of tuples containing retrieved documents and their corresponding relevance scores between 0 and 1; the list is ordered by relevance score in descending order.",
    )


class QdrantKBError(Exception):
    """Custom exception for Qdrant-related errors."""

    ...


class QdrantKBClient:
    """Wrapper around Qdrant client to handle vector storage and retrieval."""

    def __init__(self, qdrant_settings: QdrantSettings, genai_settings: GenAISettings) -> None:
        # Create logger for QdrantClient
        self.logger: Logger = getLogger("zammad-ai-index.qdrant")

        self.collection_name: str = qdrant_settings.collection_name

        self.qdrant_settings: QdrantSettings = qdrant_settings
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
            vector_name=qdrant_settings.vector_name,
        )

        self.retriever: VectorStoreRetriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": qdrant_settings.retrieval_num_documents},
        )

    async def acreate_snapshot(self) -> bool:
        """Create a snapshot of the Qdrant collection for backup purposes.

        Returns:
            bool: True if snapshot creation was successful, False otherwise.
        """
        snapshot_description: SnapshotDescription | None = await self.aclient.create_snapshot(
            collection_name=self.collection_name, wait=True
        )
        return snapshot_description is not None

    def create_snapshot(self) -> bool:
        """Create a snapshot of the Qdrant collection for backup purposes.

        Returns:
            bool: True if snapshot creation was successful, False otherwise.
        """
        snapshot_description: SnapshotDescription | None = self.client.create_snapshot(collection_name=self.collection_name, wait=True)
        return snapshot_description is not None

    async def asearch_documents(
        self,
        query: str,
        k: int | None = None,
        offset: int = 0,
    ) -> list[tuple[Document, float]]:
        """Search for relevant documents in the Qdrant collection based on a query string.

        Args:
            query (str): The query string to search for relevant documents.
            k (int, optional): The number of top relevant documents to return.
            offset (int, optional): The number of top relevant documents to skip for pagination. Defaults to 0.

        Returns:
            list[tuple[Document, float]]: A list of tuples containing relevant documents and their corresponding relevance scores between 0 and 1.
        """
        if k is None:
            k = self.qdrant_settings.retrieval_num_documents
        return await self.vectorstore.asimilarity_search_with_relevance_scores(
            query=query,
            k=k,
            offset=offset,
        )

    def search_documents(
        self,
        query: str,
        k: int | None = None,
        offset: int = 0,
    ) -> list[tuple[Document, float]]:
        """Search for relevant documents in the Qdrant collection based on a query string.

        Args:
            query (str): The query string to search for relevant documents.
            k (int, optional): The number of top relevant documents to return.
            offset (int, optional): The number of top relevant documents to skip for pagination. Defaults to 0.

        Returns:
            list[tuple[Document, float]]: A list of tuples containing relevant documents and their corresponding relevance scores between 0 and 1.
        """
        if k is None:
            k = self.qdrant_settings.retrieval_num_documents
        return self.vectorstore.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            offset=offset,
        )

    async def aadd_documents(self, content: list[str], metadata: list[dict[str, Any]], id: list[UUID | None] = []) -> None:
        """Add multiple documents to the Qdrant collection with the given content, metadata, and optional IDs.

        Args:
            content (list[str]): A list of textual content for the documents to be added.
            metadata (list[dict[str, Any]]): A list of dictionaries containing metadata associated with each document.
            id (list[UUID | None], optional): A list of optional unique identifiers for the documents. If not provided or None for an item, a UUID will be generated based on the document title. Defaults to empty list.

        Returns:
            None
        """
        ids: list[UUID | None] | list[None] = id
        if len(metadata) != len(content):
            raise ValueError("Length of 'metadata' and 'content' lists must match")
        if id == []:
            ids = [None] * len(content)
        if not len(ids) == len(metadata) == len(content):
            raise ValueError("Length of 'id' list must either match length of 'metadata' and 'content' lists or be an empty list")

        documents_to_add: list[Document] = []
        ids_to_add: list[str] = []
        for content_item, metadata_item, id_item in zip(content, metadata, ids):
            if id_item is None:
                title: str | None = metadata_item.get("title")
                if title is None:
                    raise ValueError("ID is not provided and 'title' is missing from metadata, cannot generate UUID for document")
                id_item = uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=title)
            documents_to_add.append(Document(page_content=content_item, metadata=metadata_item))
            ids_to_add.append(str(id_item))
        await self.vectorstore.aadd_documents(documents=documents_to_add, ids=ids_to_add)

    def add_documents(self, content: list[str], metadata: list[dict[str, Any]], id: list[UUID | None] = []) -> None:
        """Add multiple documents to the Qdrant collection with the given content, metadata, and optional IDs.

        Args:
            content (list[str]): A list of textual content for the documents to be added.
            metadata (list[dict[str, Any]]): A list of dictionaries containing metadata associated with each document.
            id (list[UUID | None], optional): A list of optional unique identifiers for the documents. If not provided or None for an item, a UUID will be generated based on the document title. Defaults to empty list.

        Returns:
            None
        """
        ids: list[UUID | None] | list[None] = id
        if len(metadata) != len(content):
            raise ValueError("Length of 'metadata' and 'content' lists must match")
        if id == []:
            ids = [None] * len(content)
        if not len(ids) == len(metadata) == len(content):
            raise ValueError("Length of 'id' list must either match length of 'metadata' and 'content' lists or be an empty list")

        documents_to_add: list[Document] = []
        ids_to_add: list[str] = []
        for content_item, metadata_item, id_item in zip(content, metadata, ids):
            if id_item is None:
                title: str | None = metadata_item.get("title")
                if title is None:
                    raise ValueError("ID is not provided and 'title' is missing from metadata, cannot generate UUID for document")
                id_item = uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=title)
            document = Document(page_content=content_item, metadata=metadata_item)
            documents_to_add.append(document)
            ids_to_add.append(str(id_item))
        self.vectorstore.add_documents(documents=documents_to_add, ids=ids_to_add)

    async def get_documents_by_id(self, ids: list[UUID]) -> dict[UUID, Document]:
        """Retrieve a document from the Qdrant collection by its unique identifier.

        Args:
            id (UUID): The unique identifier of the document to retrieve.
        Returns:
            Document | None: The retrieved document if found, or None if no document with the given ID exists in the collection.
        """
        try:
            results: list[Record] = self.client.retrieve(
                collection_name=self.collection_name,
                ids=ids,
            )
            if results:
                documents: dict[UUID, Document] = {}
                for result in results:
                    if result.payload and isinstance(result.id, str):
                        self.logger.debug(
                            f"Retrieved document with ID {result.id} from Qdrant: {result.payload.get('metadata', {}).get('answer_title', 'No title in metadata')}"
                        )
                        documents[UUID(result.id)] = Document(
                            page_content=result.payload.get("page_content", ""),
                            metadata=result.payload.get("metadata", {}),
                        )
                return documents
            else:
                self.logger.info(f"No documents found in Qdrant with IDs {ids}")
                return {}
        except Exception:
            self.logger.error(f"Error retrieving documents with IDs {ids} from Qdrant", exc_info=True)
            return {}

    async def close(self) -> None:
        """Close the Qdrant client connections."""
        await self.aclient.close()
        self.client.close()
