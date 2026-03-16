from pydantic import BaseModel, Field


class DocumentDict(BaseModel):
    title: str = Field(description="The title of the document.")
    url: str = Field(description="The URL source of the document.")


class StructuredAgentResponse(BaseModel):
    response: str = Field(description="The final answer to the user's question.")
    documents: list[DocumentDict] = Field(description="List of documents supporting the answer.")
