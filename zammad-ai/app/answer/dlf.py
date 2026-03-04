from __future__ import annotations

from logging import Logger

from httpx import AsyncClient, Response
from pydantic import BaseModel, Field

from app.settings.answer import DLFSettings
from app.utils.logging import getLogger

logger: Logger = getLogger("zammad-ai.answer.dlf")


class DLFAPIPayload(BaseModel):
    """Predefined payload for the DLF retrieval endpoint."""

    query: str
    categories: list[str]
    enhance_query: bool = False
    result: str = "full"
    collections: str = "all"
    rerank: bool = False


class DLFAPIResponse(BaseModel):
    """Response model for the DLF retrieval API."""

    documents: list[DLFDocument] = Field(validation_alias="retrieval_documents")


class DLFDocument(BaseModel):
    """A single retrieval document from DLF."""

    title: str = Field(validation_alias="name")
    content: str = Field(validation_alias="page_content")


class SearchDLFInput(BaseModel):
    query: str = Field(
        description="The search query string; maximum length is 200 characters (~ 20 words).",
        max_length=200,
    )


class DLFClient:
    """Stateful client for interacting with the Dienstleistungsfinder (DLF) API."""

    def __init__(self, dlf_settings: DLFSettings) -> None:
        if dlf_settings.url is None:
            raise ValueError("DLF URL must be provided for DLFClient initialization.")
        self.client = AsyncClient(
            base_url=dlf_settings.url.encoded_string(),
            timeout=dlf_settings.timeout,
        )
        self.categories: list[str] = dlf_settings.filter_categories

    async def retrieve_documents(self, query: str) -> list[DLFDocument]:
        """Retrieve relevant documents from the DLF based on a search query.

        Args:
            query (str): The search query string; maximum length is 200 characters (~ 20 words).

        Returns:
            list[DLFDocument]: The list of retrieved DLF documents.
        """
        # Create payload
        payload = DLFAPIPayload(
            query=query,
            categories=self.categories,
        )
        # Send request
        response: Response = await self.client.post(
            url="/retrieval",
            json=payload.model_dump(),
        )
        response.raise_for_status()
        # Parse response
        dlf_response: DLFAPIResponse = DLFAPIResponse.model_validate(response.json())
        return dlf_response.documents
