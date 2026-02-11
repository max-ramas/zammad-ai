# import base64
# from datetime import datetime, timezone
# from typing import Any

# import feedparser
# import httpx
# from truststore import inject_into_ssl

# from app.core.settings import get_settings
# from app.models.triage import KnowledgeBaseAnswer
# from app.utils.logging import getLogger

# from .core.core_settings import CoreSettings
# from .helper import strip_html

# logger = getLogger("zammad-ai.triage.rss_feed")

# inject_into_ssl()

# settings: CoreSettings = get_settings().core

# ZAMMAD_BASE_URL = settings.zammad.base_url
# ZAMMAD_KNOWLEDGE_BASE_ID = settings.zammad.knowledge_base_id
# KNOWLEDGE_BASE_URL = f"{ZAMMAD_BASE_URL}/api/v1/knowledge_bases/{ZAMMAD_KNOWLEDGE_BASE_ID}"
# RSS_FEED_TOKEN = settings.zammad.rss_feed_token
# AUTH_TOKEN = settings.zammad.auth_token

# # HTTP client defaults
# HTTP_TIMEOUT_SECONDS = 30


# def parse_rss_feed() -> feedparser.FeedParserDict | None:
#     """Parse an RSS feed from the given URL.

#     Args:
#         feed_url: The URL of the RSS feed to parse.

#     Returns:
#         A FeedParserDict representing the parsed feed, or None if parsing fails.
#     """
#     feed_url = f"{KNOWLEDGE_BASE_URL}/de-de/feed?token={RSS_FEED_TOKEN}"
#     try:
#         logger.debug("Fetching RSS feed from: %s", feed_url)
#         feed = feedparser.parse(feed_url)

#         # Check if feed was successfully parsed
#         if getattr(feed, "bozo", False):
#             logger.warning("Feed may have issues: %s", getattr(feed, "bozo_exception", "unknown"))

#         return feed
#     except Exception as e:
#         logger.exception("Error parsing feed from %s: %s", feed_url, e)
#         return None


# def get_ids(feed: feedparser.FeedParserDict, last_updated: datetime | None = None) -> list[str]:
#     """Extract answer IDs from a feed, optionally filtered by last_updated.

#     Args:
#         feed: Parsed feed object as returned by parse_rss_feed.
#         last_updated: If provided, only include entries updated strictly after this timestamp.

#     Returns:
#         A list of answer IDs (strings) extracted from the feed entries.
#     """
#     ids: list[str] = []

#     for entry in getattr(feed, "entries", []):
#         # Filter by last_updated if possible
#         if last_updated is not None:
#             updated = datetime.fromisoformat(entry.get("updated"))
#             # Ensure both datetimes are timezone-aware for comparison
#             if updated.tzinfo is None:
#                 updated = updated.replace(tzinfo=timezone.utc)
#             if not updated or updated <= last_updated:
#                 continue
#         raw_id = entry.get("id", "")
#         parts = raw_id.split("-")
#         answer_id = parts[-2] if len(parts) >= 2 else ""
#         if answer_id != "":
#             ids.append(answer_id)

#     return ids


# def _decode_response_content(response: httpx.Response) -> str:
#     """Decode an HTTP response to string.

#     - If content-type is JSON or text/*, returns response.text
#     - Otherwise, returns base64-encoded string of response.content
#     """
#     content_type = (response.headers.get("Content-Type") or "").lower()
#     if content_type.startswith("application/json") or content_type.startswith("text/"):
#         return response.text
#     return base64.b64encode(response.content).decode("ascii")


# def fetch_attachment_data(url: str) -> str | None:
#     """Fetch an attachment and return its content as text or base64.

#     Args:
#         url: Relative URL of the attachment (joined to ZAMMAD_BASE_URL).

#     Returns:
#         - str: Decoded text for text/* or JSON; base64 string for binary content.
#         - None: On error or if url is falsy.
#     """
#     if not url:
#         logger.warning("No URL provided for attachment fetch")
#         return None

#     full_url = f"{ZAMMAD_BASE_URL}{url}"
#     logger.info("Fetching attachment from: %s", full_url)

#     try:
#         with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
#             response = client.get(full_url)
#             response.raise_for_status()  # Raises an error for bad responses
#             return _decode_response_content(response)
#     except httpx.HTTPStatusError as e:
#         logger.error("Attachment fetch failed (%s): %s", e.response.status_code, e.response.text)
#         return None
#     except Exception as e:
#         logger.exception("Error fetching attachment from %s: %s", full_url, e)
#         return None


# def get_attachments_data(attachments: list[dict[str, Any]]) -> dict[str, str]:
#     """Fetch content for all provided attachment descriptors.

#     Args:
#         attachments: List of attachment dicts that contain a "url" key.

#     Returns:
#         List of strings (text or base64) or None entries where fetch failed.
#     """
#     results = {}
#     for attachment in attachments:
#         results[attachment["filename"]] = fetch_attachment_data(attachment["url"])
#     return results


# def get_kb_answer_by_id(answer_id: str) -> KnowledgeBaseAnswer | None:
#    """Fetch a knowledge base answer by its ID.
#
#    Args:
#        answer_id: The ID of the answer to fetch.
#
#    Returns:
#        A KnowledgeBaseAnswer instance or None if not found.
#    """
#    url = f"{KNOWLEDGE_BASE_URL}/answers/{answer_id}?include_contents={answer_id}"
#    headers = {
#        "Accept": "application/json",
#        "Content-Type": "application/json",
#        "Authorization": f"Bearer {AUTH_TOKEN}",
#    }
#    logger.info("Fetching KB answer: %s", url)
#
#    try:
#        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
#            response = client.get(url, headers=headers)
#            response.raise_for_status()
#        data = response.json()
#        assets = data.get("assets", {})
#        attachments = assets.get("KnowledgeBaseAnswer", {}).get(answer_id, {}).get("attachments", [])
#        title = assets.get("KnowledgeBaseAnswerTranslation", {}).get(answer_id, {}).get("title", "")
#        attachment_contents = get_attachments_data(attachments)
#        content = strip_html(assets.get("KnowledgeBaseAnswerTranslationContent", {}).get(answer_id, {}).get("body", ""))
#
#        return KnowledgeBaseAnswer(
#            id=answer_id,
#            title=title,
#            content=content,
#            attachments=attachment_contents,
#            url=f"{ZAMMAD_BASE_URL}/#knowledge_base/{ZAMMAD_KNOWLEDGE_BASE_ID}/locale/de-de/answer/{answer_id}",
#        )
#    except httpx.HTTPStatusError as e:
#        logger.error("KB answer fetch failed (%s) for %s: %s", e.response.status_code, answer_id, e.response.text)
#        return None
#    except Exception as e:
#        logger.exception("Error fetching KB answer %s: %s", answer_id, e)
#        return None
#
#
# def check_for_deleted_answers(ids: list[str]) -> list[str]:
#     """Check the URLs of answer IDs for any that have been deleted.

#     Args:
#         ids: List of answer IDs to check.

#     Returns:
#         List of IDs that are no longer present in the knowledge base.
#     """
#     deleted_ids = []
#     for answer_id in ids:
#         url = f"{KNOWLEDGE_BASE_URL}/answers/{answer_id}?include_contents={answer_id}"
#         headers = {
#             "Accept": "application/json",
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {AUTH_TOKEN}",
#         }
#         try:
#             with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
#                 response = client.get(url, headers=headers)
#                 if response.status_code == 404:
#                     deleted_ids.append(answer_id)
#         except Exception as e:
#             logger.exception("Error checking KB answer %s: %s", answer_id, e)
#     return deleted_ids
