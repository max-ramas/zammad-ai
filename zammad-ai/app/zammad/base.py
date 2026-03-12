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
        Parse the knowledge-base RSS feed and produce a parsed feed object.
        
        Returns:
            feedparser.FeedParserDict | None: Parsed feed data, or `None` if parsing fails or the feed is unavailable.
        """
        ...

    @abstractmethod
    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        """
        Retrieve a knowledge base answer by its Zammad answer ID.
        
        Parameters:
            answer_id (str): Zammad knowledge base answer ID.
        
        Returns:
            dict: Answer data as returned by Zammad, or `None` if no answer is found.
        """
        ...

    @abstractmethod
    async def fetch_attachment_data(self, url: str) -> str | None:
        """
        Fetch an attachment from the given relative URL and return its content as decoded text or a base64 string.
        
        Parameters:
            url (str): Relative URL of the attachment to fetch.
        
        Returns:
            str: Decoded text (for text/* MIME types) or JSON string when applicable, or a base64-encoded string for binary content.
            None: If `url` is falsy or an error occurs while fetching or decoding the attachment.
        """
        ...

    @abstractmethod
    async def check_if_answer_exists(self, answer_id: str) -> bool:
        """
        Determine whether a knowledge base answer with the given ID exists.
        
        Parameters:
            answer_id (str): ID of the knowledge base answer to check.
        
        Returns:
            bool: True if the answer exists, False otherwise.
        """
        ...


class ZammadConnectionError(Exception):
    """Custom exception for Zammad connection errors."""

    pass
