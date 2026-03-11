from asyncio import run
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Any
from uuid import UUID, uuid5

from dotenv import load_dotenv
from langchain_core.documents import Document
from src.models.qdrant import QdrantDocumentItem, QdrantVectorMetadata
from src.models.zammad import KnowledgeBaseAnswer
from src.qdrant.qdrant import ZAMMAD_AI_NAMESPACE, QdrantKBClient
from src.settings.settings import ZammadAIIndexSettings, get_settings
from src.settings.zammad import ZammadAPISettings, ZammadEAISettings
from src.utils.hash import hash_content, normalize_content
from src.utils.logging import getLogger
from src.zammad.api import ZammadAPIClient
from src.zammad.eai import ZammadEAIClient
from truststore import inject_into_ssl

settings: ZammadAIIndexSettings = get_settings()
logger: Logger = getLogger("zammad-ai-index")

inject_into_ssl()
load_dotenv()


async def retrieve_answer_ids(client: ZammadEAIClient | ZammadAPIClient) -> list[int]:
    """
    Retrieve knowledge base answer IDs for indexing.

    Depending on configuration, either performs full indexing (all answers)
    or incremental indexing based on RSS feed (recent updates only).

    Args:
        client: Zammad client instance (API or EAI)

    Returns:
        List of answer IDs to be processed

    Raises:
        No exceptions raised - errors are logged and empty list returned
    """

    if settings.index.full_indexing:
        logger.info("Performing full indexing.")
        knowledgebase = await client.kb_info()
        if knowledgebase:
            logger.info("Found %d answers in the knowledge base.", len(knowledgebase.answerIds))
            return knowledgebase.answerIds
        else:
            logger.error("Failed to fetch knowledge base information.")
            return []

    logger.info("Performing indexing based on RSS feed.")
    feed = await client.parse_rss_feed()
    if not feed:
        logger.error("Failed to parse RSS feed.")
        return []

    ids: list[int] = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.index.interval)

    for entry in getattr(feed, "entries", []):
        try:
            updated = datetime.fromisoformat(entry.get("updated"))
            # Ensure datetime is timezone-aware (UTC if naive)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)

            if updated <= cutoff_date:
                continue

            # Extract answer ID from RSS entry ID format
            entry_id = entry.get("id", "")
            parts = entry_id.split("-")
            if len(parts) >= 2:
                try:
                    answer_id = int(parts[-2])
                    ids.append(answer_id)
                except ValueError:
                    continue

        except (ValueError, TypeError):
            logger.warning("Could not parse entry %s", entry.get("id", "unknown"), exc_info=True)
            continue

    return ids


async def get_answers_data(client: ZammadEAIClient | ZammadAPIClient, answer_ids: list[int]) -> dict[int, KnowledgeBaseAnswer]:
    """
    Fetch knowledge base answer data for given answer IDs.

    Args:
        client: Zammad client instance (API or EAI)
        answer_ids: List of answer IDs to fetch
    Returns:
        Dictionary mapping answer ID to KnowledgeBaseAnswer data
    """
    answers: dict[int, KnowledgeBaseAnswer] = {}
    for answer_id in answer_ids:
        data: KnowledgeBaseAnswer | None = await client.get_kb_answer_by_id(answer_id)
        if not data:
            logger.warning("Answer with ID %d not found.", answer_id)
            continue
        answers[answer_id] = data
    return answers


async def fetch_attachments_for_answer(
    client: ZammadEAIClient | ZammadAPIClient, answer: KnowledgeBaseAnswer
) -> dict[int, tuple[str, str | None]]:
    """
    Fetch attachment data for a given knowledge base answer.

    Args:
        client: Zammad client instance (API or EAI)
        answer: KnowledgeBaseAnswer object containing attachment metadata
    Returns:
        Dictionary mapping attachment ID to its content (text or base64 string)
    """
    attachment_data: dict[int, tuple[str, str | None]] = {}
    for attachment in answer.attachments:
        if attachment.contentType.startswith("text/"):
            data = await client.fetch_kb_attachment_data(attachment.id)
            attachment_data[attachment.id] = (attachment.filename, data)
        else:
            logger.info(
                "Skipping non-text attachment %s (ID: %d) for answer ID %d due to unsupported content type: %s",
                attachment.filename,
                attachment.id,
                answer.id,
                attachment.contentType,
            )
            attachment_data[attachment.id] = (attachment.filename, None)
    return attachment_data


async def get_qdrant_data_for_answers(
    client: ZammadEAIClient | ZammadAPIClient, answers: dict[int, KnowledgeBaseAnswer]
) -> list[QdrantDocumentItem]:
    """
    Prepare data for Qdrant indexing based on knowledge base answers.

    Args:
        client: Zammad client instance (API or EAI)
        answers: Dictionary of answer ID to KnowledgeBaseAnswer objects
    Returns:
        List of QdrantDocumentItem objects containing id, content, and metadata for indexing
    """
    qdrant_data: list[QdrantDocumentItem] = []
    for answer_id, answer in answers.items():
        page_content: str = f"{answer.answerTitle} (ID: {answer.id}, Updated: {answer.updatedAt.strftime('%Y-%m-%d %H:%M:%S')}): \n\n{answer.answerBody}\n\n"

        attachment_data: dict[int, tuple[str, str | None]] = await fetch_attachments_for_answer(client, answer)
        for attachment_id, (filename, data) in attachment_data.items():
            if data:
                page_content += f"Attachment {filename} (ID: {attachment_id}):\n{data}\n\n"

        metadata: QdrantVectorMetadata = QdrantVectorMetadata(
            vector_id=uuid5(ZAMMAD_AI_NAMESPACE, answer.answerTitle),
            vector_updatedAt=datetime.now(timezone.utc),
            answer_id=answer.id,
            answer_title=answer.answerTitle,
            answer_body=answer.answerBody,
            answer_createdAt=answer.createdAt,
            answer_updatedAt=answer.updatedAt,
            answer_attachments=answer.attachments,
            answer_url=f"{settings.zammad.base_url}#knowledge_base/{settings.zammad.knowledge_base_id}/locale/de-de/answer/{answer.id}"
            if (settings.zammad.knowledge_base_id and settings.zammad.base_url)
            else None,
        )
        qdrant_data.append(QdrantDocumentItem(vector_id=metadata.vector_id, page_content=page_content, metadata=metadata))
    return qdrant_data


async def filter_for_changed_data(qdrant_client: QdrantKBClient, qdrant_data: list[QdrantDocumentItem]) -> list[QdrantDocumentItem]:
    """
    Filter the provided Qdrant data to include only entries that have changed since the last indexing.

    Args:
        qdrant_client: Instance of QdrantKBClient to query existing indexed data
        qdrant_data: List of QdrantDocumentItem objects containing id, content, and metadata for indexing
    Returns:
        Filtered list of QdrantDocumentItem objects containing only changed documents
    """
    filtered_data: list[QdrantDocumentItem] = []

    # Get vector IDs for batch lookup
    vector_ids: list[UUID] = [item.vector_id for item in qdrant_data]

    # Get all existing documents in one batch call for efficiency
    qdrant_documents: dict[UUID, Document] = await qdrant_client.get_documents_by_id(vector_ids)

    if qdrant_documents is None:
        logger.debug("No existing documents found in Qdrant, including all %d items for indexing.", len(qdrant_data))
        return qdrant_data

    for item in qdrant_data:
        new_content_hash: str = hash_content(normalize_content(item.page_content))
        item.metadata.pagecontent_hash = new_content_hash
        # Check if document exists in the dictionary
        current_document: Document | None = qdrant_documents.get(item.vector_id)

        if not current_document:
            # No existing entry, include in indexing
            logger.debug(f"No existing document found for answer ID {item.metadata.answer_id}, including in indexing.")
            filtered_data.append(item)
        else:
            if current_document.metadata.get("pagecontent_hash") != new_content_hash:
                filtered_data.append(item)
                logger.debug(f"Content changes detected for answer ID {item.vector_id}, including in re-indexing.")
            else:
                logger.debug(f"No content changes detected for answer ID {item.vector_id}, skipping re-indexing.")
    logger.info("Filtered data to %d items with detected changes for indexing.", len(filtered_data))
    return filtered_data


async def add_documents_to_qdrant(qdrant_client: QdrantKBClient, qdrant_items: list[QdrantDocumentItem]) -> None:
    """
    Add documents to Qdrant in batches.

    Args:
        qdrant_client: Instance of QdrantKBClient to add documents to
        qdrant_items: List of QdrantDocumentItem objects containing id, content, and metadata for indexing
    """
    for i in range(0, len(qdrant_items), settings.index.batch_size):
        batch: list[QdrantDocumentItem] = qdrant_items[i : i + settings.index.batch_size]

        batch_ids: list[UUID] = []
        batch_contents: list[str] = []
        batch_metadata: list[dict[str, Any]] = []

        for item in batch:
            batch_ids.append(item.vector_id)
            batch_contents.append(item.page_content)
            batch_metadata.append(item.metadata.model_dump())

        logger.info(
            f"Processing batch {i // settings.index.batch_size + 1}/{(len(qdrant_items) + settings.index.batch_size - 1) // settings.index.batch_size} with {len(batch)} documents"
        )

        await qdrant_client.aadd_documents(
            id=batch_ids,
            content=batch_contents,
            metadata=batch_metadata,
        )


async def main() -> None:
    # Initialize Zammad client based on configuration
    if isinstance(settings.zammad, ZammadAPISettings):
        zammad_client = ZammadAPIClient(settings.zammad)
    elif isinstance(settings.zammad, ZammadEAISettings):
        zammad_client = ZammadEAIClient(settings.zammad)
    else:
        raise ValueError(f"Unsupported Zammad client type: {settings.zammad.type}")

    try:
        # Determine which answer IDs to fetch based on full indexing or RSS feed
        answer_ids: list[int] = await retrieve_answer_ids(zammad_client)
        logger.info("Retrieved %d answer IDs for processing.", len(answer_ids))

        # Fetch answer data for the determined IDs
        answers: dict[int, KnowledgeBaseAnswer] = await get_answers_data(zammad_client, answer_ids)
        logger.info("Fetched data for %d answers.", len(answers))

        # Prepare data for Qdrant indexing, including fetching attachment contents
        qdrant_data: list[QdrantDocumentItem] = await get_qdrant_data_for_answers(zammad_client, answers)
        logger.info("Prepared data for %d answers for Qdrant indexing.", len(qdrant_data))

        # Initialize Qdrant client
        qdrant_client = QdrantKBClient(settings.qdrant, settings.genai)

        # Filter data to embed only changed entries since last indexing
        qdrant_items: list[QdrantDocumentItem] = await filter_for_changed_data(qdrant_client, qdrant_data)

        # Add documents to Qdrant in batches for better performance
        await add_documents_to_qdrant(qdrant_client, qdrant_items)
    except Exception:
        logger.error("An error occurred during the indexing process.", exc_info=True)
    finally:
        await zammad_client.close()


if __name__ == "__main__":
    run(main())
