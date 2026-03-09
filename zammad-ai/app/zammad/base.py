import base64
from abc import ABC, abstractmethod
from typing import Any

from feedparser import FeedParserDict
from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout, TimeoutException
from stamina import retry_context

from app.models.zammad import KnowledgeBaseAnswer, ZammadKnowledgebase, ZammadTicket
from app.utils.logging import getLogger

logger = getLogger("zammad-ai.base")


class BaseZammadClient(ABC):
    """Abstract base class for Zammad API clients."""

    @abstractmethod
    async def get_ticket(
        self,
        id: str,
    ) -> ZammadTicket:
        """
        Fetches ticket information for a given Zammad ticket ID.

        Parameters:
            id (str): Zammad ticket ID to retrieve.

        Returns:
            ZammadTicket: Ticket data corresponding to the provided ID.
        """
        ...

    @abstractmethod
    async def post_answer(
        self,
        ticket_id: str,
        text: str,
        subject: str | None = None,
        internal: bool = False,
    ) -> None:
        """
        Post an answer to the specified Zammad ticket.

        Parameters:
            ticket_id: ID of the ticket to update.
            text: Answer content to post.
            subject: Optional subject line for the answer.
            internal: If True, post as an internal note not visible to the customer.
        """
        ...

    @abstractmethod
    async def post_shared_draft(
        self,
        ticket_id: str,
        text: str,
    ) -> None:
        """
        Post a shared draft to the specified Zammad ticket.

        Parameters:
                ticket_id (str): ID of the ticket to post the shared draft to.
                text (str): Content of the shared draft.
        """
        ...

    @abstractmethod
    async def add_tag_to_ticket(
        self,
        ticket_id: str,
        tag: str,
    ) -> None:
        """
        Add a tag to the specified Zammad ticket.

        Parameters:
            ticket_id (str): Zammad ticket identifier.
            tag (str): Tag text to add to the ticket.
        """
        ...

    @abstractmethod
    async def parse_rss_feed(self) -> FeedParserDict | None:
        """
        Parse RSS feed from the knowledge base.

        Returns:
            feedparser.FeedParserDict: Parsed feed object or None if parsing fails.
        """
        ...

    @abstractmethod
    async def show_kb(self) -> ZammadKnowledgebase | None:
        """
        Fetch and return a list of knowledge base answers.

        Returns:
            list[KnowledgeBaseAnswer] | None: List of knowledge base answers or None if fetching fails.
        """
        ...

    @abstractmethod
    async def get_kb_answer_by_id(self, answer_id: str) -> KnowledgeBaseAnswer | None:
        """
        Fetch a knowledge base answer by its ID.

        Parameters:
            answer_id (str): The ID of the answer to fetch.

        Returns:
            KnowledgeBaseAnswer | None: Knowledge base answer data or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_kb_attachment_data(self, id: str) -> str | None:
        """
        Fetch an attachment and return its content as text or base64.

        Parameters:
            id (str): ID of the attachment to fetch.

        Returns:
            str: Decoded text for text/* or JSON; base64 string for binary content.
            None: On error or if id is falsy.
        """
        ...

    @abstractmethod
    async def fetch_ticket_attachment_data(self, ticket_id: str, attachment_id: str, article_id: str) -> str | None:
        """
        Fetch an attachment and return its content as text or base64.

        Parameters:
            ticket_id (str): ID of the ticket to which the attachment belongs.
            attachment_id (str): ID of the attachment to fetch.
            article_id (str): ID of the article to which the attachment belongs.

        Returns:
            str: Decoded text for text/* or JSON; base64 string for binary content.
        """
        ...

    @abstractmethod
    async def check_if_answer_exists(self, answer_id: str) -> bool:
        """
        Check if a knowledge base answer still exists.

        Parameters:
            answer_id (str): The ID of the answer to check.

        Returns:
            bool: True if answer exists, False if deleted/not found.
        """
        ...

    def __init__(self, base_url: str, timeout: int, max_retries: int, proxy_url: str | None = None) -> None:
        self.client = AsyncClient(base_url=base_url, timeout=timeout, proxy=proxy_url)
        self.http_attempts = max_retries + 1

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Make HTTP request and return JSON or text."""
        try:
            safe_methods = {"GET", "HEAD", "OPTIONS"}
            should_retry = method.upper() in safe_methods
            retry_on = (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) if should_retry else ()
            for attempt in retry_context(
                on=retry_on,
                attempts=self.http_attempts if should_retry else 1,
            ):
                with attempt:
                    response = await self.client.request(method, url, **kwargs)
                    response.raise_for_status()

                    content_type = response.headers.get("Content-Type", "").lower()
                    if content_type.startswith("application/json"):
                        return response.json()
                    elif content_type.startswith("text/"):
                        return response.text
                    else:
                        return base64.b64encode(response.content).decode("ascii")
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to execute {method} {url} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to execute {method} {url} after {self.http_attempts} attempts.") from e

    async def cleanup(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class ZammadConnectionError(Exception):
    """Custom exception for Zammad connection errors."""

    pass
