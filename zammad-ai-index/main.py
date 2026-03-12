"""Zammad AI Knowledge Base Indexing Application

This application indexes knowledge base articles from Zammad into a Qdrant vector database
for use with AI-powered ticket triage systems.

The indexing process supports both full and incremental indexing modes:
- Full indexing: Processes all knowledge base articles
- Incremental indexing: Processes only recently updated articles based on RSS feed
"""

from asyncio import run
from logging import Logger

from dotenv import load_dotenv
from src.models.qdrant import QdrantDocumentItem
from src.models.zammad import KnowledgeBaseAnswer
from src.qdrant.qdrant import QdrantKBClient
from src.services import DataProcessingService, DataRetrievalService, IndexingService
from src.settings.settings import ZammadAIIndexSettings, get_settings
from src.settings.zammad import ZammadAPISettings, ZammadEAISettings
from src.utils.logging import getLogger
from src.zammad.api import ZammadAPIClient
from src.zammad.eai import ZammadEAIClient
from truststore import inject_into_ssl

# Enable system trust store for SSL connections
inject_into_ssl()
load_dotenv()


class IndexingApplication:
    """Main application class for orchestrating the knowledge base indexing process."""

    def __init__(self) -> None:
        """Initialize the indexing application with all required services.

        Sets up Zammad client (API or EAI based on configuration), Qdrant client,
        and service layer components (data retrieval, processing, and indexing services).

        Raises:
            ValueError: If an unsupported Zammad client type is configured.

        """
        self.settings: ZammadAIIndexSettings = get_settings()
        self.logger: Logger = getLogger("zammad-ai-index")

        # Initialize Zammad client based on configuration
        if isinstance(self.settings.zammad, ZammadAPISettings):
            self.zammad_client = ZammadAPIClient(self.settings.zammad)
            self.logger.info("Initialized Zammad API-Client")
        elif isinstance(self.settings.zammad, ZammadEAISettings):
            self.zammad_client = ZammadEAIClient(self.settings.zammad)
            self.logger.info("Initialized Zammad EAI-Client")
        else:
            raise ValueError(f"Unsupported Zammad client type: {self.settings.zammad.type}")

        # Initialize Qdrant client
        self.qdrant_client: QdrantKBClient = QdrantKBClient(
            self.settings.qdrant,
            self.settings.genai,
        )
        self.logger.info("Initialized Qdrant client")

        # Initialize services
        self.data_retrieval_service: DataRetrievalService = DataRetrievalService(self.zammad_client)
        self.data_processing_service: DataProcessingService = DataProcessingService(
            base_url=self.settings.zammad.base_url,
            knowledge_base_id=self.settings.zammad.knowledge_base_id,
        )
        self.indexing_service: IndexingService = IndexingService(qdrant_client=self.qdrant_client)
        self.logger.info("Initialized all services")

    async def run_indexing(self) -> None:
        """Execute the complete indexing workflow.

        Performs a four-step process:
        1. Retrieve answer IDs for processing (full or incremental based on settings)
        2. Fetch detailed answer data from Zammad
        3. Prepare and filter data for Qdrant (only changed documents)
        4. Add documents to Qdrant vector database in batches

        The method handles errors gracefully and ensures cleanup of resources.
        Process completion status is logged at info level.

        Raises:
            Exception: Critical errors during indexing are logged and re-raised.

        """
        self.logger.info("Starting indexing process...")

        try:
            # Step 0: Create Qdrant snapshot
            snapshot_success: bool = await self.qdrant_client.acreate_snapshot()

            if snapshot_success:
                self.logger.info("Successfully created Qdrant snapshot before indexing.")
            else:
                self.logger.warning("Failed to create Qdrant snapshot before indexing. Exiting.")
                return

            # Step 1: Retrieve answer IDs for processing
            answer_ids: list[int] = await self.data_retrieval_service.retrieve_answer_ids()

            if not answer_ids:
                self.logger.warning("No answer IDs found for processing. Exiting.")
                return
            else:
                self.logger.info("Retrieved %d answer IDs for processing.", len(answer_ids))

            # Step 2: Fetch detailed answer data
            answers: dict[int, KnowledgeBaseAnswer] = await self.data_retrieval_service.get_answers_data(answer_ids)

            if not answers:
                self.logger.warning("No answer data retrieved. Exiting.")
                return
            else:
                self.logger.info("Fetched data for %d answers.", len(answers))

            # Step 3: Prepare and filter data for Qdrant
            qdrant_items: list[QdrantDocumentItem] = await self._prepare_and_filter_data(answers)

            if not qdrant_items:
                self.logger.info("No new or changed documents to index.")
                return
            else:
                self.logger.info("Prepared %d documents for Qdrant indexing.", len(qdrant_items))

            # Step 4: Add documents to Qdrant
            success: bool = await self.indexing_service.add_documents_to_qdrant(qdrant_items)

            if success:
                self.logger.info("Indexing process completed successfully!")
            else:
                self.logger.error("Indexing process completed with errors.")

        except Exception:
            self.logger.error("Critical error during indexing process", exc_info=True)
            raise
        finally:
            await self.cleanup()

    async def _prepare_and_filter_data(self, answers: dict[int, KnowledgeBaseAnswer]) -> list[QdrantDocumentItem]:
        """Prepare data for Qdrant and filter for changed documents only.

        Transforms knowledge base answers into Qdrant document format with metadata,
        then filters to include only documents that have changed since last indexing
        to avoid unnecessary re-processing.

        Args:
            answers: Dictionary mapping answer IDs to KnowledgeBaseAnswer objects

        Returns:
            List of QdrantDocumentItem objects ready for indexing, containing only
            new or changed documents based on content hash comparison.

        """
        # Prepare data for Qdrant indexing
        qdrant_data = await self.data_processing_service.prepare_qdrant_data(
            client=self.zammad_client,
            answers=answers,
            retrieval_service=self.data_retrieval_service,
        )
        self.logger.info("Prepared data for %d answers for Qdrant indexing.", len(qdrant_data))

        # Filter to only include changed documents
        filtered_items = await self.data_processing_service.filter_for_changed_data(
            qdrant_client=self.qdrant_client,
            qdrant_data=qdrant_data,
        )

        return filtered_items

    async def cleanup(self) -> None:
        """Clean up resources and close connections.

        Properly closes Zammad client and Qdrant client connections to prevent
        resource leaks. This method is called in the finally block of run_indexing
        to ensure cleanup occurs even if errors are encountered.
        """
        if self.zammad_client:
            await self.zammad_client.close()
            self.logger.debug("Closed Zammad client connection")

        if self.qdrant_client:
            await self.qdrant_client.close()
            self.logger.debug("Closed Qdrant client connection")


async def main() -> None:
    """Main application entry point.

    Creates and runs the IndexingApplication, handling any critical errors
    that occur during the indexing process. All exceptions are logged with
    full traceback information before the application exits.
    """
    try:
        app = IndexingApplication()
        await app.run_indexing()
    except Exception:
        getLogger("zammad-ai-index").error("Application encountered a critical error", exc_info=True)


if __name__ == "__main__":
    run(main())
