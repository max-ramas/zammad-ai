from logging import Logger

from langchain_core.documents import Document
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

from app.utils.logging import getLogger

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
