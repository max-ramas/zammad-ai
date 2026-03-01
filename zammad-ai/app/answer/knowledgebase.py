from logging import Logger

from langchain.tools import ToolException, ToolRuntime, tool
from langchain_core.documents import Document
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

from app.qdrant import QdrantKBClient, QdrantKBError
from app.utils.logging import getLogger

from .context import AgentContext

logger: Logger = getLogger("zammad-ai.answer.knowledgebase")


class SearchQdrantKBInput(BaseModel):
    query: str = Field(
        description="The search query string; should be concise and focused on the information needed; maximum length is 200 characters (~ 20 words).",
        max_length=200,
    )
    num_documents: PositiveInt = Field(
        default=5,
        description="The number of relevant documents to retrieve; should be a positive integer; default is 5.",
    )
    offset: NonNegativeInt = Field(
        default=0,
        description="The number of top relevant documents to skip for pagination; should be a non-negative integer; default is 0. Good for retrieving the next set of results in subsequent calls with the same query.",
    )


class RetrieveDocumentsKBOutput(BaseModel):
    documents_with_relevance_score: list[tuple[Document, float]] = Field(
        description="A list of tuples containing retrieved documents and their corresponding relevance scores between 0 and 1; the list is ordered by relevance score in descending order.",
    )


@tool(
    "search_internal_knowledgebase",
    description="Retrieve relevant documents for a query from the knowledge base.",
    args_schema=SearchQdrantKBInput,
    parse_docstring=False,
    response_format="content",
)
async def search_knowledgebase(
    runtime: ToolRuntime[AgentContext],
    query: str,
    num_documents: int = 5,
    offset: int = 0,
) -> RetrieveDocumentsKBOutput:
    """
    Retrieve relevant documents based on a query.

    Args:
        query (str): The search query string.

    Returns:
        RetrieveDocumentsKBOutput: A dictionary containing lists of retrieved documents.

    Raises:
        ToolException: If the retrieval process fails.
    """
    qdrant_client: QdrantKBClient = runtime.context.qdrant_kb_client
    try:
        relevant_documents_with_scores: list[tuple[Document, float]] = await qdrant_client.asearch_documents(
            query=query,
            k=num_documents,
            offset=offset,
        )
        return RetrieveDocumentsKBOutput(documents_with_relevance_score=relevant_documents_with_scores)
    except QdrantKBError as e:
        logger.error("Error retrieving documents from Qdrant", exc_info=e)
        raise ToolException("Failed to retrieve documents from Knowledge Base") from e
