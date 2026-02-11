from ag_ui_langgraph import LangGraphAgent
from langchain_core.runnables.config import RunnableConfig
from langfuse import observe
from truststore import inject_into_ssl

from app.core.settings import ZammadAISettings, get_settings
from app.observe.observer import LangfuseClient
from app.utils.logging import getLogger

from .agent import StructuredAgentResponse, build_agent

inject_into_ssl()

settings: ZammadAISettings = get_settings()

logger = getLogger("zammad-ai.answer")
langfuse_client = LangfuseClient()


@observe(name="Zammad-AI Formulate Answer", as_type="span")
async def formulate_answer(
    question: str,
    category: str,
    session_id: str | None = None,
) -> StructuredAgentResponse:
    if session_id is None:
        session_id = langfuse_client.generate_session_id()
    text = f"Kategorie: {category}\n {question}"
    langfuse_client.langfuse.update_current_trace(session_id=session_id)
    config: RunnableConfig = langfuse_client.build_config(session_id=session_id)
    agent: LangGraphAgent = await build_agent(callbacks=[langfuse_client.langfuse_handler])
    agent_result = await agent.graph.ainvoke(input={"messages": [{"role": "user", "content": text}]}, config=config)
    return agent_result["structured_response"]
