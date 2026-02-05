from logging import Logger
from typing import Any

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


class StructuredAgentResponse(BaseModel):
    response: str = Field(description="The final answer to the user's question.")
    documents: list[dict[str, Any]] = Field(description="List of documents supporting the answer.")


async def build_agent(callbacks: Callbacks) -> LangGraphAgent:
    """Build and return the Zammad AI Answer agent."""

    # Build the chat model
    chat_model = ChatOpenAI(
        model=settings.triage.openai.completions_model,
        temperature=settings.triage.openai.temperature,
        max_retries=5,
        api_key=settings.triage.openai.api_key,  # type: ignore
        base_url=settings.triage.openai.url,
    )

    # Configure the tools
    available_tools: list[BaseTool] = [retrieve_documents_dlf, retrieve_documents_knowledgebase]

    system_prompt: str = """
        You are the ZAMMAD AI Agent, an AI assistant designed to answer tickets from the citizens of Munich. 
        Your goal is to answer questions accurately and concisely using the information available to you.
        
        Tools:
        You have access to the following tools to assist you in your tasks:
        1. retrieve_documents_knowledgebase: Use this tool to search the knowledge base for relevant documents to subcategories of Questions based on a query.
        2. retrieve_documents_dlf: Use this tool to search the Dienstleistungsfinder for relevant pages on services of the city of munich based on a query.
    """

    # Create the agent via the factory method
    agent = create_agent(
        model=chat_model,
        system_prompt=system_prompt,
        tools=available_tools,
        response_format=ProviderStrategy(StructuredAgentResponse),
        # context_schema=AgentContext,  # type: ignore
    )

    # Context usage probably supported in future LangGraphAgent versions
    # agent_result = await agent.ainvoke(
    #     input={"messages": [{"role": "user", "content": "Wird in München über eine Zweitwohnungssteuer diskutiert?"}]},
    #     config={
    #         "configurable": {"thread_id": uuid4(), "vectorstore": vectorstore},
    #         "callbacks": callbacks,
    #     },
    #     # context=AgentContext(vectorstore=vectorstore, db_sessionmaker=db_sessionmaker),
    # )

    # logger.info(f"Agent test invocation result: {agent_result}")

    # Wrap the agent in a AG-UI LangGraphAgent
    return LangGraphAgent(
        name="Zammad-AI Answer Agent",
        description="Der Zammad-AI Answer Agent unterstützt bei der Recherche und Analyse von Dokumenten und formuliert präzise Antworten.",
        graph=agent,  # type: ignore
        config={
            "callbacks": callbacks,
        },  # Workaround as LangGraphAgent doesnt yet support context parameter
    )
