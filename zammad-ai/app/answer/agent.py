from logging import Logger

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentState, _InputAgentState, _OutputAgentState
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from app.models.answer import StructuredAgentResponse
from app.settings import GenAISettings
from app.utils.logging import getLogger

from .context import AgentContext
from .dlf import search_dlf
from .knowledgebase import search_knowledgebase

logger: Logger = getLogger("zammad-ai.answer.agent")


def build_agent(
    genai_settings: GenAISettings,
    system_prompt: str,
) -> CompiledStateGraph[AgentState[StructuredAgentResponse], AgentContext, _InputAgentState, _OutputAgentState[StructuredAgentResponse]]:  # type: ignore
    """Build and return the Zammad AI Answer agent."""

    # Build the chat model
    chat_model = ChatOpenAI(
        model_name=genai_settings.answer_model or genai_settings.chat_model,
        temperature=genai_settings.temperature,
        max_retries=genai_settings.max_retries,
    )

    # Configure the tools
    available_tools: list[BaseTool] = [
        search_dlf,
        search_knowledgebase,
    ]

    # Create the agent via the factory method
    agent: CompiledStateGraph[
        AgentState[StructuredAgentResponse], AgentContext, _InputAgentState, _OutputAgentState[StructuredAgentResponse]  # type: ignore
    ] = create_agent(
        model=chat_model,
        system_prompt=system_prompt,
        tools=available_tools,
        response_format=StructuredAgentResponse,
        context_schema=AgentContext,
    )

    return agent
