from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from langfuse import observe
from truststore import inject_into_ssl

from app.core.settings import Settings, get_settings
from app.observe.observer import _build_config, get_session_id, setup_langfuse
from app.utils.logging import getLogger

inject_into_ssl()

settings: Settings = get_settings()

logger = getLogger(__name__)
(langfusehandler, langfuse, _, _, _) = setup_langfuse(settings.triage)


@observe(name="Zammad-AI Formulate Answer", as_type="span")
async def call_llm(
    input: dict,
    system_prompt: str,
    session_id: str | None = None,
):
    if session_id is None:
        session_id = get_session_id()
    reasoning_config = None
    if settings.triage.openai.reasoning_effort is not None:
        reasoning_config = {"effort": settings.triage.openai.reasoning_effort, "summary": "auto"}
    chat_model = ChatOpenAI(
        model=settings.triage.openai.completions_model,
        temperature=settings.triage.openai.temperature,
        store=False,
        max_retries=5,
        api_key=settings.triage.openai.api_key,  # type: ignore
        base_url=settings.triage.openai.url,
        reasoning=reasoning_config if reasoning_config else None,
    )
    categorize_template = ChatPromptTemplate(
        messages=[
            ("system", system_prompt),
            ("user", "{text}"),
        ]
    )
    langfuse.update_current_trace(session_id=session_id)
    config = _build_config(session_id=session_id, langfuse_handler=langfusehandler)  # type: ignore

    chain = RunnableSequence(categorize_template, chat_model)
    response = await chain.ainvoke(
        input=input,
        config=config,
    )
    return response


def _get_data_from_vector_db(question: str) -> str:
    # Placeholder function to simulate data retrieval from a vector database
    # In a real implementation, this would query the vector DB and return relevant information
    return ""


async def formulate_answer(
    question: str,
    category: str,
    session_id: str | None = None,
) -> str:
    if session_id is None:
        session_id = get_session_id()
    text = f"Kategorie: {category}\n {question}"
    # data = _get_data_from_vector_db(text)

    result = await call_llm(
        input={"text": text, "data": _get_data_from_vector_db(text)},
        system_prompt="You are an expert assistant working at the drivers lisence authority of the city of Munich. Please provide accurate and helpful information. Formulate your answer based on the following context:\n\n{data}\n\nQuestion: {text}\n\nJust answer the question directly. Just respond with the answer. NO additional explanations. Always answer in German. Always answer from the perspective of the drivers lisence authority of the city of Munich. Be poluite and professional as writing a Email.",
        session_id=session_id,
    )

    return result.content
