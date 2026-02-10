import asyncio
from datetime import datetime, timedelta, timezone

from app.models.qdrant import QdrantVectorMetadata
from app.qdrant.qdrant import save_to_qdrant
from app.triage.rss_feed import get_ids, get_kb_answer_by_id, parse_rss_feed
from app.utils.logging import getLogger

INTERVALL = 1  # days


async def main() -> None:
    feed = parse_rss_feed()
    logger = getLogger("zammad-ai.update_qdrant")

    if feed:
        ids: list[str] = get_ids(feed, datetime.now(timezone.utc) - timedelta(days=INTERVALL))
        logger.info("Found %d updated answers in the last %d days.", len(ids), INTERVALL)

        for answer_id in ids:
            logger.info("Answer ID: %s", answer_id)
            answer = get_kb_answer_by_id(answer_id)
            if answer:
                page_content = answer.title + "\n\n" + answer.content + "\n\n"
                for filename, attachment_content in (answer.attachments or {}).items():
                    page_content += f"Attachment {filename} \n" + attachment_content + "\n\n"
                metadata: QdrantVectorMetadata = QdrantVectorMetadata(
                    id=str(answer.id),
                    title=answer.title,
                    content=answer.content,
                    attachments=answer.attachments,
                    url=answer.url,
                )

                await save_to_qdrant(page_content=page_content, metadata=metadata, id=str(answer.id))
            else:
                logger.warning("Answer with ID %s not found.", answer_id)


if __name__ == "__main__":
    asyncio.run(main())
