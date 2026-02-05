from logging import Logger
from typing import TypedDict

import httpx
from langchain.tools import ToolException, tool
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from app.qdrant.qdrant import get_similar_vectors
from app.utils.logging import getLogger

logger: Logger = getLogger()


class RetrieveDocumentsArgs(BaseModel):
    query: str = Field(description="The search query string.")


class RetrieveDocumentsKBOutput(TypedDict):
    documents: list[Document]


class DLFPage(BaseModel):
    id: str = Field(description="The page ID.")
    title: str = Field(description="The page title.")
    content: str = Field(description="The page content.")


class RetrieveDocumentsDLFOutput(TypedDict):
    pages: list[DLFPage]


class WriteAnswerArgs(BaseModel):
    question: str = Field(description="The question to answer.")
    kb_documents: list[Document] = Field(description="List of documents from the knowledge base.")
    dlf_pages: list[DLFPage] = Field(description="List of pages from the Dienstleistungsfinder.")


@tool(
    description="Retrieve relevant documents for a query from the knowledge base.",
    args_schema=RetrieveDocumentsArgs,
    parse_docstring=False,
    response_format="content",
)
async def retrieve_documents_knowledgebase(query: str) -> RetrieveDocumentsKBOutput:
    """
    Retrieve relevant documents based on a query.

    Args:
        query (str): The search query string.

    Returns:
        RetrieveDocumentsOutput: A dictionary containing lists of retrieved documents.
    """
    # raise ToolException("DB down - try again later.")
    try:
        logger.info(f"Retrieving documents for query: {query}")

        docs: list[Document] = await get_similar_vectors(query, k=5)
        logger.debug(f"Retrieved {len(docs)} documents:\n{[doc.metadata for doc in docs]}")

        return RetrieveDocumentsKBOutput(documents=docs)
    except Exception as e:
        logger.error(f"Error in retrieve_documents tool: {e}", exc_info=True)
        raise ToolException(f"Failed to retrieve documents: {str(e)}")


@tool(
    description="Retrieve relevant documents for a query from the Diensleistungsfinder.",
    args_schema=RetrieveDocumentsArgs,
    parse_docstring=False,
    response_format="content",
)
async def retrieve_documents_dlf(query: str) -> RetrieveDocumentsDLFOutput:
    """
    Retrieve relevant documents based on a query from the Dienstleistungsfinder.

    Args:
        query (str): The search query string.
    Returns:
        RetrieveDocumentsDLFOutput: A dictionary containing lists of retrieved documents.
    """

    async with httpx.AsyncClient() as client:
        result = await client.post(
            "https://dlf-backend-dev-dlf-dev.apps.test.capk.muenchen.de/api/retrieval",
            json={
                "query": query,
                "categories": ["fahrerlaubnis und führerschein"],
                "result": "full",
                "collections": "all",
                "rerank": True,
            },
        )
        json = result.json()
        output = RetrieveDocumentsDLFOutput(pages=[])
        for doc in json.get("retrieval_documents", []):
            output["pages"].append(
                DLFPage(
                    id=doc["id"],
                    title=doc["name"],
                    content=doc["page_content"],
                )
            )

        return output
