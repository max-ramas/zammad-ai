from asyncio import run
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_DNS, UUID, uuid5

from dotenv import load_dotenv
from langchain_core.documents import Document
from src.models.qdrant import QdrantVectorMetadata
from src.models.zammad import KnowledgeBaseAnswer
from src.qdrant.qdrant import QdrantKBClient
from src.settings.settings import get_settings
from src.settings.zammad import ZammadAPISettings, ZammadEAISettings
from src.utils.logging import getLogger
from src.zammad.api import ZammadAPIClient
from src.zammad.eai import ZammadEAIClient
from truststore import inject_into_ssl

settings = get_settings()
logger = getLogger("zammad-ai.update_qdrant")
ZAMMAD_AI_NAMESPACE: UUID = uuid5(
    namespace=NAMESPACE_DNS,
    name="zammad-ai.muenchen.de",
)
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
        attachment_data[attachment.id] = (attachment.filename, await client.fetch_kb_attachment_data(attachment.id))
    return attachment_data


async def get_qdrant_data_for_answers(
    client: ZammadEAIClient | ZammadAPIClient, answers: dict[int, KnowledgeBaseAnswer]
) -> list[tuple[str, QdrantVectorMetadata]]:
    """
    Prepare data for Qdrant indexing based on knowledge base answers.

    Args:
        client: Zammad client instance (API or EAI)
        answers: Dictionary of answer ID to KnowledgeBaseAnswer objects
    Returns:
        List of tuples containing page content and corresponding Qdrant metadata
    """
    qdrant_data: list[tuple[str, QdrantVectorMetadata]] = []
    for answer_id, answer in answers.items():
        page_content: str = answer.answerTitle + "\n" + answer.answerBody + "\n\n"

        attachment_data: dict[int, tuple[str, str | None]] = await fetch_attachments_for_answer(client, answer)
        for attachment_id, (filename, data) in attachment_data.items():
            if data:
                page_content += f"Attachment {filename}:\n{data}\n\n"
            else:
                logger.warning(f"Failed to fetch data for attachment {attachment_id} of answer {answer_id}")

        metadata: QdrantVectorMetadata = QdrantVectorMetadata(
            id=uuid5(ZAMMAD_AI_NAMESPACE, answer.answerTitle),
            answer_info=answer,
            url=f"{settings.zammad.base_url}/de-de/knowledge_bases/{settings.zammad.knowledge_base_id}/answers/{answer_id}",
        )
        qdrant_data.append((page_content, metadata))
    return qdrant_data


async def filter_for_changed_data(
    qdrant_client: QdrantKBClient, qdrant_data: list[tuple[str, QdrantVectorMetadata]]
) -> list[tuple[str, QdrantVectorMetadata]]:
    """
    Filter the provided Qdrant data to include only entries that have changed since the last indexing.

    Args:
        qdrant_client: Instance of QdrantKBClient to query existing indexed data
        qdrant_data: List of tuples containing page content and corresponding Qdrant metadata
    Returns:
        Filtered list of tuples containing only changed page content and corresponding Qdrant metadata
    """
    filtered_data: list[tuple[str, QdrantVectorMetadata]] = []
    for page_content, metadata in qdrant_data:
        existing_entry: Document | None = qdrant_client.get_document_by_id(metadata.id)
        if not existing_entry:
            # No existing entry, include in indexing
            filtered_data.append((page_content, metadata))
        else:
            # Compare content and key metadata fields to determine if content has changed

            # Compare page content first (most likely to change)
            if existing_entry.page_content != page_content:
                filtered_data.append((page_content, metadata))
                logger.info(f"Content changes detected for answer ID {metadata.id}, including in re-indexing.")
                continue

            # Compare answer info from metadata if content is the same
            existing_answer_info = existing_entry.metadata.get("answer_info") if isinstance(existing_entry.metadata, dict) else None
            new_answer_info = metadata.answer_info.model_dump()

            if existing_answer_info != new_answer_info:
                filtered_data.append((page_content, metadata))
                logger.info(f"Metadata changes detected for answer ID {metadata.id}, including in re-indexing.")
            else:
                logger.info(f"No changes detected for answer ID {metadata.id}, skipping re-indexing.")

    return filtered_data


async def main() -> None:
    # Initialize Zammad client based on configuration
    if isinstance(settings.zammad, ZammadAPISettings):
        client = ZammadAPIClient(settings.zammad)
    elif isinstance(settings.zammad, ZammadEAISettings):
        client = ZammadEAIClient(settings.zammad)
    else:
        raise ValueError(f"Unsupported Zammad client type: {settings.zammad.type}")

    # Determine which answer IDs to fetch based on full indexing or RSS feed
    answer_ids: list[int] = await retrieve_answer_ids(client)
    logger.info("Retrieved %d answer IDs for processing.", len(answer_ids))

    # Fetch answer data for the determined IDs
    answers: dict[int, KnowledgeBaseAnswer] = await get_answers_data(client, answer_ids)
    logger.info("Fetched data for %d answers.", len(answers))

    # Prepare data for Qdrant indexing, including fetching attachment contents
    qdrant_data: list[tuple[str, QdrantVectorMetadata]] = await get_qdrant_data_for_answers(client, answers)
    logger.info("Prepared data for %d answers for Qdrant indexing.", len(qdrant_data))

    # Initialize Qdrant client
    qdrant_client = QdrantKBClient(settings.qdrant, settings.genai)

    # Filter data to embed only changed entries since last indexing
    qdrant_data: list[tuple[str, QdrantVectorMetadata]] = await filter_for_changed_data(qdrant_client, qdrant_data)

    # Add documents to Qdrant
    for page_content, metadata in qdrant_data:
        await qdrant_client.aadd_document(
            content=page_content,
            metadata=metadata.model_dump(),
            id=metadata.id,
        )

    await client.close()


if __name__ == "__main__":
    run(main())
