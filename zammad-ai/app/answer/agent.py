from logging import Logger

from ag_ui_langgraph import LangGraphAgent
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.tools import BaseTool
from langchain_core.callbacks import Callbacks
from langchain_openai import ChatOpenAI

from app.core.settings import ZammadAISettings, get_settings
from app.models.answer import StructuredAgentResponse
from app.utils.logging import getLogger

from .tools import retrieve_documents_dlf, retrieve_documents_knowledgebase

settings: ZammadAISettings = get_settings()
logger: Logger = getLogger()


async def build_agent(callbacks: Callbacks) -> LangGraphAgent:
    """Build and return the Zammad AI Answer agent."""

    # Build the chat model
    chat_model = ChatOpenAI(
        model_name=settings.genai.chat_model,
        temperature=settings.genai.temperature,
        max_retries=settings.genai.max_retries,
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
        # context_schema=AgentContext,
    )

    # Wrap the agent in a AG-UI LangGraphAgent
    return LangGraphAgent(
        name="Zammad-AI Answer Agent",
        description="Der Zammad-AI Answer Agent unterstützt bei der Recherche und Analyse von Dokumenten und formuliert präzise Antworten.",
        graph=agent,
        config={
            "callbacks": callbacks,
        },  # Workaround as LangGraphAgent doesnt yet support context parameter
    )
