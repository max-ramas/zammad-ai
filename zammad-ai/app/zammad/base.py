from abc import ABC, abstractmethod

import feedparser

from app.models.zammad import ZammadTicket


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
        internal: bool = False,
    ) -> None:
        """
        Post an answer to the specified Zammad ticket.

        Parameters:
            ticket_id: ID of the ticket to update.
            text: Answer content to post.
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
    async def cleanup(self) -> None:
        """
        Perform cleanup of client resources (e.g., closing connections).
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


class ZammadConnectionError(Exception):
    """Custom exception for Zammad connection errors."""

    pass
