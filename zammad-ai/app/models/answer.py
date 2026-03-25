"""API response and agent output models for the answer workflow."""

from pydantic import BaseModel, Field


class DocumentDict(BaseModel):
    """Reference document included with an answer response."""

    title: str = Field(description="The title of the document.")
    url: str = Field(description="The URL source of the document.")


class StructuredAgentResponse(BaseModel):
    """Structured response returned by the answer agent."""

    response: str = Field(description="The final answer to the user's question.")
    documents: list[DocumentDict] = Field(description="List of documents supporting the answer.")
