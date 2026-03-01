import asyncio
from datetime import datetime, timedelta, timezone

import feedparser

from app.models.qdrant import QdrantVectorMetadata
from app.models.zammad import KnowledgeBaseAnswer
from app.qdrant import QdrantKBClient
from app.settings.settings import get_settings
from app.settings.zammad import ZammadAPISettings, ZammadEAISettings
from app.utils.logging import getLogger
from app.zammad.api import ZammadAPIClient
from app.zammad.eai import ZammadEAIClient

INTERVALL = 100  # days
settings = get_settings()
logger = getLogger("zammad-ai.update_qdrant")


def get_ids(feed: feedparser.FeedParserDict, last_updated: datetime | None = None) -> list[str]:
    """Extract answer IDs from a feed, optionally filtered by last_updated.

    Args:
        feed: Parsed feed object as returned by parse_rss_feed.
        last_updated: If provided, only include entries updated strictly after this timestamp.

    Returns:
        A list of answer IDs (strings) extracted from the feed entries.
    """
    ids: list[str] = []

    for entry in getattr(feed, "entries", []):
        # Filter by last_updated if possible
        if last_updated is not None:
            try:
                updated = datetime.fromisoformat(entry.get("updated"))
            except Exception as e:
                logger.warning("Could not parse updated time for entry %s: %s", entry.get("id", "unknown"), e)
                continue
            # Ensure both datetimes are timezone-aware for comparison
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated <= last_updated:
                continue
        raw_id = entry.get("id", "")
        parts = raw_id.split("-")
        answer_id = parts[-2] if len(parts) >= 2 else ""
        if answer_id != "":
            ids.append(answer_id)

    return ids


async def main() -> None:
    qdrant_client = QdrantKBClient(settings.qdrant, settings.genai)
    if isinstance(settings.zammad, ZammadAPISettings):
        client = ZammadAPIClient(settings.zammad)
    elif isinstance(settings.zammad, ZammadEAISettings):
        client = ZammadEAIClient(settings.zammad)
    else:
        raise ValueError(f"Unsupported Zammad client type: {settings.zammad.type}")
    try:
        feed = await client.parse_rss_feed()

        if feed:
            ids: list[str] = get_ids(feed, datetime.now(timezone.utc) - timedelta(days=INTERVALL))
            logger.info("Found %d updated answers in the last %d days.", len(ids), INTERVALL)

            for answer_id in ids:
                logger.info("Answer ID: %s", answer_id)
                answer_data = await client.get_kb_answer_by_id(answer_id)
                if answer_data:
                    try:
                        # Create KnowledgeBaseAnswer instance from dictionary data
                        answer = KnowledgeBaseAnswer(
                            id=str(answer_data.get("id", answer_id)),
                            title=answer_data.get("title", ""),
                            content=answer_data.get("content", ""),
                            attachments=answer_data.get("attachments", {}),
                        )

                        page_content = answer.title + "\n\n" + answer.content + "\n\n"
                        for filename, attachment_content in (answer.attachments or {}).items():
                            page_content += f"Attachment {filename} \n" + attachment_content + "\n\n"

                        # Construct URL for the knowledge base answer
                        if isinstance(settings.zammad, ZammadAPISettings):
                            answer_url = (
                                f"{settings.zammad.base_url}/de-de/knowledge_bases/{settings.zammad.knowledge_base_id}/answers/{answer_id}"
                            )
                        elif isinstance(settings.zammad, ZammadEAISettings):
                            answer_url = (
                                f"{settings.zammad.eai_url}/de-de/knowledge_bases/{settings.zammad.knowledge_base_id}/answers/{answer_id}"
                            )
                        else:
                            answer_url = "URL not available due to missing configuration"

                        metadata: QdrantVectorMetadata = QdrantVectorMetadata(
                            id=answer.id,
                            title=answer.title,
                            content=answer.content,
                            attachments=answer.attachments,
                            url=answer_url,
                        )

                        await qdrant_client.aadd_document(
                            content=page_content,
                            metadata=metadata,  # type: ignore
                            id=answer.id,
                        )
                    except Exception as e:
                        logger.error("Failed to process KB answer %s: %s", answer_id, e, exc_info=True)
                else:
                    logger.warning("Answer with ID %s not found.", answer_id)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
