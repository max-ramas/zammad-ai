"""Service for retrieving data from Zammad knowledge base."""

from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Any
from uuid import UUID

from feedparser import FeedParserDict
from qdrant_client.models import Record
from src.models.zammad import KnowledgeBaseAnswer, ZammadKnowledgebase
from src.settings.settings import ZammadAIIndexSettings, get_settings
from src.utils.logging import getLogger
from src.zammad.api import ZammadAPIClient
from src.zammad.eai import ZammadEAIClient


class DataRetrievalService:
    """Service responsible for retrieving knowledge base data from Zammad.

    Handles both full and incremental data retrieval modes:
    - Full indexing: Retrieves all knowledge base answers
    - Incremental indexing: Uses RSS feed to identify recently updated answers

    Supports both Zammad API and EAI client interfaces for flexible integration.
    """

    def __init__(self, client: ZammadAPIClient | ZammadEAIClient) -> None:
        """Initialize the data retrieval service.

        Sets up the service with the provided Zammad client and loads application
        settings for configuring indexing behavior (full vs incremental mode).

        Args:
            client: Configured Zammad client instance (either API or EAI implementation)
        """
        self.logger: Logger = getLogger("zammad-ai-index.data-retrieval")
        self.client: ZammadAPIClient | ZammadEAIClient = client
        self.settings: ZammadAIIndexSettings = get_settings()

    async def retrieve_answer_ids(self) -> list[int]:
        """Retrieve knowledge base answer IDs for indexing.

        Depending on application configuration, either performs full indexing (all answers)
        or incremental indexing based on RSS feed (recent updates only). The indexing
        mode and interval are controlled by the application settings.

        Returns:
            List of knowledge base answer IDs to be processed for indexing

        Note:
            Errors are handled gracefully - failures are logged and an empty list
            is returned rather than raising exceptions.

        """
        if self.settings.index.full_indexing:
            return await self._get_all_answer_ids()

        return await self._get_recent_answer_ids_from_rss(self.settings.index.interval)

    async def _get_all_answer_ids(self) -> list[int]:
        """Retrieve all knowledge base answer IDs.

        Fetches the complete list of answer IDs from the knowledge base
        for full indexing operations. Used when incremental indexing is disabled.

        Returns:
            List of all answer IDs in the knowledge base, or empty list if
            the knowledge base information cannot be retrieved.

        """
        self.logger.info("Performing full indexing.")

        knowledgebase: ZammadKnowledgebase | None = await self.client.kb_info()
        if knowledgebase:
            self.logger.info("Found %d answers in the knowledge base.", len(knowledgebase.answerIds))
            return knowledgebase.answerIds

        self.logger.error("Failed to fetch knowledge base information.")
        return []

    async def _get_recent_answer_ids_from_rss(self, interval_days: int) -> list[int]:
        """Retrieve recent answer IDs from RSS feed.

        Parses the knowledge base RSS feed to identify answers that have been
        updated within the specified time interval. Used for incremental indexing
        to avoid processing unchanged content.

        Args:
            interval_days: Number of days to look back from current time

        Returns:
            List of answer IDs that have been updated within the interval,
            or empty list if RSS feed cannot be parsed or no recent updates found.

        """
        self.logger.info("Performing indexing based on RSS feed.")

        feed: FeedParserDict | None = await self.client.parse_rss_feed()
        if not feed:
            self.logger.error("Failed to parse RSS feed.")
            return []

        ids: list[int] = []
        cutoff_date: datetime = datetime.now(timezone.utc) - timedelta(days=interval_days)

        for entry in getattr(feed, "entries", []):
            try:
                updated_str = entry.get("updated")
                if not updated_str:
                    self.logger.debug("Entry %s has no 'updated' field, skipping.", entry.get("id", "unknown"))
                    continue
                updated: datetime = datetime.fromisoformat(updated_str)
                # Ensure datetime is timezone-aware (UTC if naive)
                if updated.tzinfo is None:
                    updated: datetime = updated.replace(tzinfo=timezone.utc)

                if updated <= cutoff_date:
                    continue

                # Extract answer ID from RSS entry ID format
                answer_id: int | None = self._get_answer_id_from_entry(entry)
                if answer_id:
                    ids.append(answer_id)

            except (ValueError, TypeError):
                self.logger.warning("Could not parse entry %s", entry.get("id", "unknown"), exc_info=True)
                continue

        self.logger.info("Found %d recent answers from RSS feed.", len(ids))
        return ids

    def _get_answer_id_from_entry(self, entry: FeedParserDict) -> int | None:
        """Extract answer ID from RSS entry ID format.

        Parses the RSS entry ID string to extract the numeric answer ID.
        The ID format follows a pattern where the answer ID is the second-to-last
        component when split by hyphens.

        Args:
            entry: RSS feed entry dictionary containing the 'id' field

        Returns:
            Extracted numeric answer ID, or None if the ID format is invalid
            or cannot be parsed as an integer.

        """
        id_parts: list[str] = entry.get("id", "").split("-")
        if len(id_parts) >= 2:
            try:
                return int(id_parts[-2])
            except ValueError:
                pass
        return None

    async def get_answers_data(self, answer_ids: list[int]) -> dict[int, KnowledgeBaseAnswer]:
        """Fetch knowledge base answer data for given answer IDs.

        Args:
            answer_ids: List of answer IDs to fetch

        Returns:
            Dictionary mapping answer ID to KnowledgeBaseAnswer data

        """
        answers: dict[int, KnowledgeBaseAnswer] = {}

        for answer_id in answer_ids:
            data: KnowledgeBaseAnswer | None = await self.client.get_kb_answer_by_id(answer_id)
            if not data:
                self.logger.warning("Answer with ID %d not found.", answer_id)
                continue
            answers[answer_id] = data

        self.logger.info("Successfully fetched data for %d/%d answers.", len(answers), len(answer_ids))
        return answers

    async def fetch_attachments_for_answer(self, answer: KnowledgeBaseAnswer) -> dict[int, tuple[str, str | None]]:
        """Fetch attachment data for a given knowledge base answer.

        Args:
            answer: KnowledgeBaseAnswer object containing attachment metadata

        Returns:
            Dictionary mapping attachment ID to tuple of (filename, content)
            Content is None for unsupported file types

        """
        attachment_data: dict[int, tuple[str, str | None]] = {}

        for attachment in answer.attachments:
            if attachment.contentType.startswith("text/"):
                data = await self.client.fetch_kb_attachment_data(attachment.id)
                attachment_data[attachment.id] = (attachment.filename, data)
            else:
                self.logger.info(
                    "Skipping non-text attachment %s (ID: %d) for answer ID %d due to unsupported content type: %s",
                    attachment.filename,
                    attachment.id,
                    answer.id,
                    attachment.contentType,
                )
                attachment_data[attachment.id] = (attachment.filename, None)

        return attachment_data

    async def retrieve_deleted_answer_ids(self, all_points: list[Record]) -> list[UUID]:
        """Retrieve IDs of knowledge base answers that have been deleted since last indexing.

        This method checks for answers that were previously indexed but have been
        removed from the knowledge base, allowing the indexing process to also
        handle deletions and keep the search index in sync with the current state
        of the knowledge base.

        Returns:
            List of answer IDs that have been deleted since the last indexing run,
            or empty list if no deletions are detected or if retrieval fails.

        """

        try:
            deleted_ids: list[UUID] = []
            for point in all_points:
                payload: dict[str, Any] | None = point.payload
                if not payload:
                    self.logger.warning("Point with ID %s has no payload, skipping deletion check.", point.id)
                    continue

                metadata = payload.get("metadata")
                if not metadata:
                    self.logger.warning("Point with ID %s has no metadata, skipping deletion check.", point.id)
                    continue

                answer_id: int | None = metadata.get("answer_id")
                if answer_id is not None:
                    if not await self.client.check_if_answer_exists(int(answer_id)):
                        self.logger.debug("Answer ID %d no longer exists in knowledge base, marking for deletion.", answer_id)
                        deleted_ids.append(UUID(str(point.id)))

            self.logger.info("Retrieved %d deleted answer IDs.", len(deleted_ids))
            return deleted_ids
        except Exception:
            self.logger.error("Failed to retrieve deleted answer IDs.", exc_info=True)
            return []
