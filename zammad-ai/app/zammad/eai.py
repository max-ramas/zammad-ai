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
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        raise NotImplementedError("ZammadEAIClient is not implemented yet.")
