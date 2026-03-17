"""Service for orchestrating the knowledge base indexing process."""

from logging import Logger
from typing import Any
from uuid import UUID

from job.models.qdrant import QdrantDocumentItem
from job.qdrant.qdrant import QdrantKBClient
from job.settings.settings import ZammadAIIndexSettings, get_settings
from job.utils.logging import getLogger

logger: Logger = getLogger("zammad-ai-index.indexing")
settings: ZammadAIIndexSettings = get_settings()


def add_documents_to_qdrant(qdrant_items: list[QdrantDocumentItem], qdrant_client: QdrantKBClient) -> bool:
    """Add documents to Qdrant in batches for optimal performance.

    Args:
        qdrant_items: List of QdrantDocumentItem objects containing id, content, and metadata for indexing
        qdrant_client: Instance of QdrantKBClient for interacting with Qdrant


    Returns:
        True if all documents were successfully added, False otherwise

    """
    if not qdrant_items:
        logger.info("No documents to add to Qdrant.")
        return True

    batch_size: int = settings.index.batch_size

    total_batches: int = (len(qdrant_items) + batch_size - 1) // batch_size
    successful_batches: int = 0

    logger.info("Starting to add %d documents to Qdrant in %d batches.", len(qdrant_items), total_batches)

    for i in range(0, len(qdrant_items), batch_size):
        batch_number: int = i // batch_size + 1
        batch: list[QdrantDocumentItem] = qdrant_items[i : i + batch_size]

        try:
            success: bool = _process_batch(batch, batch_number, total_batches, qdrant_client)
            if success:
                successful_batches += 1
            else:
                logger.error("Failed to process batch %d/%d", batch_number, total_batches)
        except Exception:
            logger.error("Exception occurred while processing batch %d/%d", batch_number, total_batches, exc_info=True)

    logger.info("Successfully processed %d/%d batches.", successful_batches, total_batches)
    return successful_batches == total_batches


def _process_batch(batch: list[QdrantDocumentItem], batch_number: int, total_batches: int, qdrant_client: QdrantKBClient) -> bool:
    """Process a single batch of documents.

    Prepares batch data by extracting IDs, content, and metadata, then uploads
    the batch to Qdrant. Provides detailed logging of batch processing progress
    and handles any exceptions that occur during the upload.

    Args:
        batch: List of QdrantDocumentItem objects to process in this batch
        batch_number: Current batch number (1-indexed) for progress tracking
        total_batches: Total number of batches for progress reporting

    Returns:
        True if batch was processed successfully, False if any errors occurred

    """
    try:
        batch_ids, batch_contents, batch_metadata = _prepare_batch_data(batch)

        logger.info("Processing batch %d/%d with %d documents", batch_number, total_batches, len(batch))

        qdrant_client.add_documents(
            id=batch_ids,
            content=batch_contents,
            metadata=batch_metadata,
        )

        logger.debug("Successfully added batch %d/%d to Qdrant", batch_number, total_batches)
        return True

    except Exception:
        logger.error("Failed to add batch %d/%d to Qdrant", batch_number, total_batches, exc_info=True)
        return False


def _prepare_batch_data(batch: list[QdrantDocumentItem]) -> tuple[list[UUID | None], list[str], list[dict[str, Any]]]:
    """Prepare batch data for Qdrant insertion.

    Extracts vector IDs, page content, and metadata from QdrantDocumentItem
    objects and organizes them into separate lists as required by the
    Qdrant client's aadd_documents method.

    Args:
        batch: List of QdrantDocumentItem objects to prepare for insertion

    Returns:
        Tuple containing three aligned lists:
        - vector_ids: List of UUID identifiers for each document
        - contents: List of string content for each document
        - metadata: List of metadata dictionaries for each document

    """
    batch_ids: list[UUID | None] = []
    batch_contents: list[str] = []
    batch_metadata: list[dict[str, Any]] = []

    for item in batch:
        batch_ids.append(item.vector_id)
        batch_contents.append(item.page_content)
        batch_metadata.append(item.metadata.model_dump(mode="json"))

    return batch_ids, batch_contents, batch_metadata
