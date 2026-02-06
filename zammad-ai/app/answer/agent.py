from logging import Logger

from ag_ui_langgraph import LangGraphAgent
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.tools import BaseTool
from langchain_core.callbacks import Callbacks
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings
from app.utils.logging import getLogger

from .tools import retrieve_documents_dlf, retrieve_documents_knowledgebase

settings: Settings = get_settings()
logger: Logger = getLogger()


class DocumentDict(BaseModel):
    title: str = Field(description="The title of the document.")
    url: str = Field(description="The URL source of the document.")


class StructuredAgentResponse(BaseModel):
    response: str = Field(description="The final answer to the user's question.")
    documents: list[DocumentDict] = Field(description="List of documents supporting the answer.")


async def build_agent(callbacks: Callbacks) -> LangGraphAgent:
    """Build and return the Zammad AI Answer agent."""

    # Build the chat model
    chat_model = ChatOpenAI(
        model=settings.core.openai.completions_model,
        temperature=settings.core.openai.temperature,
        max_retries=5,
        api_key=settings.core.openai.api_key,  # type: ignore
        base_url=settings.core.openai.url,
    )

    # Configure the tools
    available_tools: list[BaseTool] = [retrieve_documents_dlf, retrieve_documents_knowledgebase]

    system_prompt: str = settings.answer.answer_agent_prompt

    # Create the agent via the factory method
    agent = create_agent(
        model=chat_model,
        system_prompt=system_prompt,
        tools=available_tools,
        response_format=ProviderStrategy(StructuredAgentResponse),
        # context_schema=AgentContext,  # type: ignore
    )

    # Wrap the agent in a AG-UI LangGraphAgent
    return LangGraphAgent(
        name="Zammad-AI Answer Agent",
        description="Der Zammad-AI Answer Agent unterstützt bei der Recherche und Analyse von Dokumenten und formuliert präzise Antworten.",
        graph=agent,  # type: ignore
        config={
            "callbacks": callbacks,
        },  # Workaround as LangGraphAgent doesnt yet support context parameter
    )
