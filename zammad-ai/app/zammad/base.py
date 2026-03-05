import base64
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, TypeVar, cast

import feedparser
from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout, TimeoutException
from stamina import retry_context

from app.models.zammad import ZammadTicket
from app.utils.logging import getLogger

F = TypeVar("F", bound=Callable[..., Any])
logger = getLogger("zammad-ai.base")


def with_retry(func: F) -> F:
    """Decorator to add retry logic to HTTP methods."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        method_name = func.__name__
        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    return await func(self, *args, **kwargs)
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to execute {method_name} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to execute {method_name} after {self.http_attempts} attempts.") from e

    return cast(F, wrapper)


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
    async def parse_rss_feed(self) -> feedparser.FeedParserDict | None:
        """
        Parse RSS feed from the knowledge base.

        Returns:
            feedparser.FeedParserDict: Parsed feed object or None if parsing fails.
        """
        ...

    @abstractmethod
    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        """
        Fetch a knowledge base answer by its ID.

        Parameters:
            answer_id (str): The ID of the answer to fetch.

        Returns:
            dict: Knowledge base answer data or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_attachment_data(self, url: str) -> str | None:
        """
        Fetch an attachment and return its content as text or base64.

        Parameters:
            url (str): Relative URL of the attachment.

        Returns:
            str: Decoded text for text/* or JSON; base64 string for binary content.
            None: On error or if url is falsy.
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

    @with_retry
    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Make HTTP request and return JSON or text."""
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if content_type.startswith("application/json"):
            return response.json()
        elif content_type.startswith("text/"):
            return response.text
        else:
            return base64.b64encode(response.content).decode("ascii")

    async def cleanup(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class ZammadConnectionError(Exception):
    """Custom exception for Zammad connection errors."""

    pass
