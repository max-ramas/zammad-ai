from pydantic import BaseModel

from app.qdrant import QdrantKBClient

from .dlf import DLFClient


class AgentContext(BaseModel):
    qdrant_kb_client: QdrantKBClient
    dlf_client: DLFClient
