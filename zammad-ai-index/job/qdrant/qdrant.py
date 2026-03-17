from logging import Logger
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import ApiException
from qdrant_client.http.models import CollectionInfo
from qdrant_client.http.models.models import Record
from qdrant_client.models import SnapshotDescription
from src.settings.genai import GenAISettings
from src.settings.settings import QdrantSettings, ZammadAIIndexSettings
from src.utils.logging import getLogger

# Create a consistent namespace UUID for generating vector IDs based on content
ZAMMAD_AI_NAMESPACE: UUID = uuid5(
    namespace=NAMESPACE_DNS,
    name="zammad-ai.muenchen.de",
)


class QdrantKBError(Exception):
    """Custom exception for Qdrant-related errors."""

    ...


class QdrantKBClient:
    """Wrapper around Qdrant client to handle vector storage and retrieval."""

    def __init__(self, settings: ZammadAIIndexSettings) -> None:
        # Create logger for QdrantClient
        self.logger: Logger = getLogger("zammad-ai-index.qdrant")

        self.collection_name: str = settings.qdrant.collection_name
        self.settings: ZammadAIIndexSettings = settings
        self.qdrant_settings: QdrantSettings = settings.qdrant
        self.genai_settings: GenAISettings = settings.genai
        # Create sync + async Qdrant client with appropriate configuration
        self.client = QdrantClient(
            url=self.qdrant_settings.url.encoded_string(),
            port=None,  # Port is included in the URL, so we set it to None
            timeout=self.qdrant_settings.timeout,
            api_key=self.qdrant_settings.api_key.get_secret_value() if self.qdrant_settings.api_key else None,
        )
        self.aclient = AsyncQdrantClient(
            url=self.qdrant_settings.url.encoded_string(),
            port=None,  # Port is included in the URL, so we set it to None
            timeout=self.qdrant_settings.timeout,
            api_key=self.qdrant_settings.api_key.get_secret_value() if self.qdrant_settings.api_key else None,
        )

        # Check if collection exists and if there is data in it, else raise an Error
        try:
            if not self.client.collection_exists(collection_name=self.qdrant_settings.collection_name):
                self.logger.error(f"Qdrant collection '{self.qdrant_settings.collection_name}' does not exist.")
                raise QdrantKBError(f"Qdrant collection '{self.qdrant_settings.collection_name}' does not exist.")

            collection_info: CollectionInfo = self.client.get_collection(collection_name=self.qdrant_settings.collection_name)
            if collection_info.points_count == 0:
                self.logger.warning(f"Qdrant collection '{self.qdrant_settings.collection_name}' exists but is empty.")

        except ApiException as e:
            self.logger.error("Error checking Qdrant collection existence or retrieving collection info", exc_info=True)
            raise QdrantKBError("Failed to check Qdrant collection existence or retrieve collection info") from e

        # Create LangChain embedding model
        self.embeddings: Embeddings

        match self.genai_settings.sdk:
            case "openai":
                from langchain_openai import OpenAIEmbeddings

                self.embeddings = OpenAIEmbeddings(
                    model=self.genai_settings.embedding_model,
                    dimensions=self.qdrant_settings.vector_dimension,
                    max_retries=self.genai_settings.max_retries,
                )
            case _:
                self.logger.error(f"Unsupported GenAI SDK '{self.genai_settings.sdk}' for embeddings")
                raise QdrantKBError(f"Unsupported GenAI SDK '{self.genai_settings.sdk}' for embeddings")

        # Test embedding to ensure configuration is correct
        test_result: list[float] = self.embeddings.embed_query("This is a test string")
        if len(test_result) != self.qdrant_settings.vector_dimension:
            self.logger.error(
                f"Embedding dimension mismatch: expected {self.qdrant_settings.vector_dimension}, got {len(test_result)}. Check your GenAI embedding model configuration."
            )
            raise QdrantKBError(
                f"Embedding dimension mismatch: expected {self.qdrant_settings.vector_dimension}, got {len(test_result)}. Check your GenAI embedding model configuration."
            )

        # Create LangChain Qdrant vector store
        self.vectorstore = QdrantVectorStore(
            client=self.client,
            collection_name=self.qdrant_settings.collection_name,
            embedding=self.embeddings,
            vector_name=self.qdrant_settings.vector_name,
        )

        self.retriever: VectorStoreRetriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.qdrant_settings.retrieval_num_documents},
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
                answer_id: str | None = metadata_item.get("answer_id")
                kb_id: str | None = self.settings.zammad.knowledge_base_id
                if answer_id is None or kb_id is None:
                    raise ValueError("ID is not provided and required metadata is missing, cannot generate UUID for document")
                id_item: UUID = uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=f"KB-{kb_id}-Answer-{answer_id}")
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
                answer_id: str | None = metadata_item.get("answer_id")
                kb_id: str | None = self.settings.zammad.knowledge_base_id
                if answer_id is None or kb_id is None:
                    raise ValueError("ID is not provided and required metadata is missing, cannot generate UUID for document")
                id_item: UUID = uuid5(namespace=ZAMMAD_AI_NAMESPACE, name=f"KB-{kb_id}-Answer-{answer_id}")
            document = Document(page_content=content_item, metadata=metadata_item)
            documents_to_add.append(document)
            ids_to_add.append(str(id_item))
        self.vectorstore.add_documents(documents=documents_to_add, ids=ids_to_add)

    async def get_documents_by_ids(self, ids: list[UUID]) -> dict[UUID, Document]:
        """Retrieve a document from the Qdrant collection by its unique identifier.

        Args:
            ids (list[UUID]): The unique identifiers of the documents to retrieve.
        Returns:
            dict[UUID, Document]: A dictionary mapping the provided UUIDs to their corresponding Document objects. If a document with a given UUID is not found, it will not be included in the returned dictionary.
        Raises:
            QdrantKBError: If there is an error during retrieval from Qdrant, a QdrantKBError will be raised with details about the failure.
        """
        try:
            results: list[Record] = await self.aclient.retrieve(
                collection_name=self.collection_name,
                ids=[str(id) for id in ids],
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
        except Exception as e:
            self.logger.error(f"Error retrieving documents with IDs {ids} from Qdrant", exc_info=True)
            raise QdrantKBError("Failed to retrieve documents from Qdrant") from e

    async def close(self) -> None:
        """Close the Qdrant client connections."""
        await self.aclient.close()
        self.client.close()

    async def delete_points_by_ids(self, ids: list) -> None:
        """Delete documents from the Qdrant collection by their unique identifiers.

        Args:
            ids (list[UUID]): The unique identifiers of the documents to delete.
        Returns:
            None
        Raises:
            QdrantKBError: If there is an error during deletion from Qdrant, a QdrantKBError will be raised with details about the failure.
        """
        try:
            await self.aclient.delete(
                collection_name=self.collection_name,
                points_selector=ids,
            )
            self.logger.info(f"Deleted documents with IDs {ids} from Qdrant")
        except Exception as e:
            self.logger.error(f"Error deleting documents with IDs {ids} from Qdrant", exc_info=True)
            raise QdrantKBError("Failed to delete documents from Qdrant") from e

    async def get_all_points(self) -> list[Record]:
        """Retrieve all points from the Qdrant collection.
        Returns:
            list[Record]: A list of Record objects representing all points in the Qdrant collection. Each Record includes the point's ID, payload, and vector (if available).
        Raises:
            QdrantKBError: If there is an error during retrieval from Qdrant, a QdrantKBError will be raised with details about the failure.
        """
        try:
            # Retrieve all document IDs from Qdrant and convert them to integers
            all_points: list[Record] = []
            next_offset = None

            while True:
                points, next_offset = await self.aclient.scroll(
                    collection_name=self.collection_name,
                    limit=500,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                if not points:
                    break

                all_points.extend(points)

                if next_offset is None:
                    break

            return all_points
        except Exception as e:
            self.logger.error("Error retrieving all answer IDs from Qdrant", exc_info=True)
            raise QdrantKBError("Failed to retrieve all points from Qdrant") from e
