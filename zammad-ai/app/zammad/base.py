from abc import ABC, abstractmethod

from app.models.zammad import ZammadTicket


class BaseZammadClient(ABC):
    """Abstract base class for Zammad API clients."""

    @abstractmethod
    async def get_ticket(
        self,
        id: str,
    ) -> ZammadTicket:
        """Fetch ticket information from Zammad by ticket ID.

        Args:
            id (str): The ID of the ticket to fetch.
        Returns:
            ZammadTicket: The ticket information retrieved from Zammad.
        """
        ...

    @abstractmethod
    async def post_answer(
        self,
        ticket_id: str,
        text: str,
        internal: bool = False,
    ) -> None:
        """Post an answer to a Zammad ticket.

        Args:
            ticket_id (str): The ID of the ticket to which the answer should be posted.
            text (str): The content of the answer to be posted.
            internal (bool): Whether the answer should be posted as an internal note (default: False).
        """
        ...

    @abstractmethod
    async def post_shared_draft(
        self,
        ticket_id: str,
        text: str,
    ) -> None:
        """Post a shared draft to a Zammad ticket.

        Args:
            ticket_id (str): The ID of the ticket to which the shared draft should be posted.
            text (str): The content of the shared draft to be posted.
        """
        ...

    @abstractmethod
    async def add_tag_to_ticket(
        self,
        ticket_id: str,
        tag: str,
    ) -> None:
        """Add a tag to a Zammad ticket.

        Args:
            ticket_id (str): The ID of the ticket to which the tag should be added.
            tag (str): The tag to be added to the ticket.
        """
        ...


class ZammadConnectionError(Exception):
    """Custom exception for Zammad connection errors."""

    pass
