import feedparser

from app.core.settings.zammad import ZammadEAISettings
from app.models.zammad import ZammadTicket

from .base import BaseZammadClient


class ZammadEAIClient(BaseZammadClient):
    """Zammad API client implementation for Zammad AI."""

    def __init__(self, settings: ZammadEAISettings):
        """Initialize the ZammadEAIClient with the provided settings.

        Args:
            settings (ZammadEAISettings): The settings for Zammad EAI integration, including API endpoint and authentication details.
        """
        ...

    async def get_ticket(self, id: str) -> ZammadTicket:
        """
        Retrieve a ticket from Zammad by its identifier.

        Parameters:
            id (str): Zammad ticket identifier.

        Returns:
            ZammadTicket: The ticket corresponding to the provided identifier.

        Raises:
            NotImplementedError: If the client implementation is not available.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        """
        Post an answer message to a Zammad ticket.

        Parameters:
            ticket_id (str): The identifier of the ticket to post the message to.
            text (str): The message content to add to the ticket.
            internal (bool): If True, post the message as an internal note; otherwise post it as a visible customer reply.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        """
        Posts a shared draft message to the specified Zammad ticket.

        Parameters:
            ticket_id (str): Identifier of the ticket to attach the shared draft to.
            text (str): Draft message content to post.

        Raises:
            NotImplementedError: Implementation not provided in this client stub.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        """
        Add a tag to the specified Zammad ticket.

        Parameters:
                ticket_id (str): Identifier of the ticket to update.
                tag (str): Tag value to add to the ticket.

        Raises:
                NotImplementedError: Implementation is not provided in this client.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def cleanup(self) -> None:
        """
        Perform cleanup of client resources.
        """
        pass

    async def parse_rss_feed(self) -> feedparser.FeedParserDict | None:
        """
        Parse RSS feed from the knowledge base.

        Returns:
            feedparser.FeedParserDict: Parsed feed object or None if parsing fails.

        Raises:
            NotImplementedError: Implementation not provided in this client stub.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        """
        Fetch a knowledge base answer by its ID.

        Parameters:
            answer_id (str): The ID of the answer to fetch.

        Returns:
            dict: Knowledge base answer data or None if not found.

        Raises:
            NotImplementedError: Implementation not provided in this client stub.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def fetch_attachment_data(self, url: str) -> str | None:
        """
        Fetch an attachment and return its content as text or base64.

        Parameters:
            url (str): Relative URL of the attachment.

        Returns:
            str: Decoded text for text/* or JSON; base64 string for binary content.
            None: On error or if url is falsy.

        Raises:
            NotImplementedError: Implementation not provided in this client stub.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def check_if_answer_exists(self, answer_id: str) -> bool:
        """
        Check if a knowledge base answer still exists.

        Parameters:
            answer_id (str): The ID of the answer to check.

        Returns:
            bool: True if answer exists, False if deleted/not found.

        Raises:
            NotImplementedError: Implementation not provided in this client stub.
        """
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")
