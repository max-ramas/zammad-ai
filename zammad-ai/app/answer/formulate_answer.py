from ag_ui_langgraph import LangGraphAgent
from langchain_core.runnables.config import RunnableConfig
from langfuse import observe
from truststore import inject_into_ssl

from app.core.settings import Settings, get_settings
from app.observe.observer import _build_config, get_session_id, setup_langfuse
from app.utils.logging import getLogger

from .agent import StructuredAgentResponse, build_agent

inject_into_ssl()

settings: Settings = get_settings()

logger = getLogger(__name__)
(langfusehandler, langfuse, _, _, _) = setup_langfuse(settings)


@observe(name="Zammad-AI Formulate Answer", as_type="span")
async def formulate_answer(
    question: str,
    category: str,
    session_id: str | None = None,
) -> StructuredAgentResponse:
    if session_id is None:
        session_id = get_session_id()
    text = f"Kategorie: {category}\n {question}"
    langfuse.update_current_trace(session_id=session_id)
    config: RunnableConfig = _build_config(session_id=session_id, langfuse_handler=langfusehandler)  # type: ignore
    agent: LangGraphAgent = await build_agent(callbacks=langfusehandler)
    agent_result = await agent.graph.ainvoke(input={"messages": [{"role": "user", "content": text}]}, config=config)
    return agent_result["structured_response"]
