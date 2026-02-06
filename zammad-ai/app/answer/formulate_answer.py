from truststore import inject_into_ssl

from app.core.settings import Settings, get_settings
from app.observe.observer import get_session_id, setup_langfuse
from app.utils.logging import getLogger

from .agent import StructuredAgentResponse, build_agent

inject_into_ssl()

settings: Settings = get_settings()

logger = getLogger(__name__)
(langfusehandler, langfuse, _, _, _) = setup_langfuse(settings)


async def formulate_answer(
    question: str,
    category: str,
    session_id: str | None = None,
) -> StructuredAgentResponse:
    if session_id is None:
        session_id = get_session_id()
    text = f"Kategorie: {category}\n {question}"
    agent = await build_agent(callbacks=langfusehandler)
    agent_result = await agent.graph.ainvoke(
        input={"messages": [{"role": "user", "content": text}]},
        config={
            "callbacks": [langfusehandler],
        },
    )
    return agent_result["structured_response"]
