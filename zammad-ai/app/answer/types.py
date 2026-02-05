from langchain_qdrant import QdrantVectorStore
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.util.typing import TypedDict


class AgentContext(TypedDict):
    vectorstore: QdrantVectorStore
    db_sessionmaker: async_sessionmaker
