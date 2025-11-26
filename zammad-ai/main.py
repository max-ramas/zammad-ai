from time import perf_counter

from app.models.triage import TriageResult
from app.triage.rss_feed import get_ids, get_kb_answer_by_id, parse_rss_feed
from app.triage.triage import perform_triage
from app.utils.logging import getLogger
from dotenv import load_dotenv
from truststore import inject_into_ssl

load_dotenv()

inject_into_ssl()

logger = getLogger("zammad-ai.main")


async def main():
    ticket_id = "3735"
    start = perf_counter()
    result: TriageResult = await perform_triage(ticket_id)
    elapsed = perf_counter() - start

    logger.info("Triage result: %s", result)
    logger.info("perform_triage duration: %.3f s", elapsed)


def test_rss_feed_parsing():
    feed = parse_rss_feed()
    if feed is None:
        logger.error("Failed to parse RSS feed.")
    else:
        ids = get_ids(feed)
        for answer_id in ids:
            logger.info("Fetched KB answer: %s", get_kb_answer_by_id(answer_id))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
