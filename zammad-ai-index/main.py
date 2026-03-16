"""Zammad AI Knowledge Base Indexing Application

This application indexes knowledge base articles from Zammad into a Qdrant vector database
for use with AI-powered ticket triage systems.

The indexing process supports both full and incremental indexing modes:
- Full indexing: Processes all knowledge base articles
- Incremental indexing: Processes only recently updated articles based on RSS feed
"""

from asyncio import run
from logging import Logger
from uuid import UUID

from dotenv import load_dotenv
from qdrant_client.models import Record
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
            self.settings,
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

            # Step3: Get all points from Qdrant
            all_points: list[Record] = await self.qdrant_client.get_all_points()

            # Step 4: Prepare and filter data for Qdrant
            qdrant_items: list[QdrantDocumentItem] = await self._prepare_and_filter_data(answers, all_points)

            # Step 5: Check for deleted documents
            deleted_answer_ids: list[UUID] = await self.data_retrieval_service.retrieve_deleted_answer_ids(all_points)

            if not qdrant_items:
                self.logger.info("No new or changed documents to index.")
                if deleted_answer_ids:
                    self.logger.info("However, %d deleted answer IDs detected that will be removed from Qdrant.", len(deleted_answer_ids))
                else:
                    self.logger.info("No deleted answer IDs detected. Exiting.")
                    return
            else:
                self.logger.info("Prepared %d documents for Qdrant indexing.", len(qdrant_items))

            # Step 6: Create Qdrant snapshot
            snapshot_success: bool = await self.qdrant_client.acreate_snapshot()

            if snapshot_success:
                self.logger.info("Successfully created Qdrant snapshot before indexing.")
            else:
                self.logger.warning("Failed to create Qdrant snapshot before indexing. Exiting.")
                return

            # Step 7: Add documents to Qdrant
            if qdrant_items:
                success: bool = await self.indexing_service.add_documents_to_qdrant(qdrant_items)

                if success:
                    self.logger.info("Successfully indexed documents into Qdrant.")
                else:
                    self.logger.error("Failed to index documents into Qdrant.")
                    return

            # Step 8: Delete documents from Qdrant for deleted answer IDs
            if deleted_answer_ids:
                try:
                    await self.qdrant_client.delete_points_by_ids(deleted_answer_ids)
                    self.logger.info("Successfully deleted %d documents from Qdrant for deleted answer IDs.", len(deleted_answer_ids))
                except Exception:
                    self.logger.error("Failed to delete points for deleted answer IDs: %s", deleted_answer_ids, exc_info=True)

            self.logger.info("Indexing process completed successfully.")

        except Exception:
            self.logger.error("Critical error during indexing process", exc_info=True)
            raise
        finally:
            await self.cleanup()

    async def _prepare_and_filter_data(self, answers: dict[int, KnowledgeBaseAnswer], all_points: list[Record]) -> list[QdrantDocumentItem]:
        """Prepare data for Qdrant and filter for changed documents only.

        Transforms knowledge base answers into Qdrant document format with metadata,
        then filters to include only documents that have changed since last indexing
        to avoid unnecessary re-processing.

        Args:
            answers: Dictionary mapping answer IDs to KnowledgeBaseAnswer objects
            all_points: List of all points in the Qdrant collection

        Returns:
            List of QdrantDocumentItem objects ready for indexing, containing only
            new or changed documents based on content hash comparison.

        """
        # Prepare data for Qdrant indexing
        qdrant_data: list[QdrantDocumentItem] = await self.data_processing_service.prepare_qdrant_data(
            answers=answers,
            retrieval_service=self.data_retrieval_service,
        )
        self.logger.info("Prepared data for %d answers for Qdrant indexing.", len(qdrant_data))

        # Filter to only include changed documents
        filtered_items: list[QdrantDocumentItem] = await self.data_processing_service.filter_for_changed_data(
            new_qdrant_data=qdrant_data,
            all_points=all_points,
        )

        return filtered_items

    async def cleanup(self) -> None:
        """Clean up resources and close connections.

        Properly closes Zammad client and Qdrant client connections to prevent
        resource leaks. This method is called in the finally block of run_indexing
        to ensure cleanup occurs even if errors are encountered.
        """
        cleanup_errors: list[Exception] = []

        if self.zammad_client:
            try:
                await self.zammad_client.close()
                self.logger.debug("Closed Zammad client connection")
            except Exception as e:
                self.logger.error("Failed to close Zammad client connection", exc_info=True)
                cleanup_errors.append(e)

        if self.qdrant_client:
            try:
                await self.qdrant_client.close()
                self.logger.debug("Closed Qdrant client connection")
            except Exception as e:
                self.logger.error("Failed to close Qdrant client connection", exc_info=True)
                cleanup_errors.append(e)

        if cleanup_errors:
            self.logger.warning("Cleanup finished with %d error(s).", len(cleanup_errors))


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
        raise


if __name__ == "__main__":
    run(main())
