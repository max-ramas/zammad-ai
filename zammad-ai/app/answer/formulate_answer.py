from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableSequence
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from truststore import inject_into_ssl

from app.core.settings import get_settings
from app.models.triage import (
    CategorizationResult,
)
from app.triage.prompts import SYSTEM_PROMPT_ANSWER
from app.utils.logging import getLogger

inject_into_ssl()

settings = get_settings()

_formulation_chain = None

logger = getLogger(__name__)


async def _get_formulation_chain() -> RunnableSequence:
    """Get or create the formulation chain with caching."""
    global _formulation_chain

    if _formulation_chain is None:
        formulation_template = ChatPromptTemplate(
            messages=[
                ("system", SYSTEM_PROMPT_ANSWER),
                ("user", "{question}"),
            ]
        )

        chat_model = ChatOpenAI(
            model=settings.triage.openai.completions_model,
            temperature=settings.triage.openai.temperature,
            max_retries=settings.triage.openai.max_retries,
            api_key=SecretStr(settings.triage.openai.api_key),
            base_url=settings.triage.openai.url,
        )

        structured_chat_model: Runnable = chat_model.with_structured_output(schema=CategorizationResult, strict=True)
        _formulation_chain = RunnableSequence(formulation_template, structured_chat_model)

        logger.debug("Formulation chain initialized")

    return _formulation_chain


def _get_data_from_vector_db(question: str) -> str:
    # Placeholder function to simulate data retrieval from a vector database
    # In a real implementation, this would query the vector DB and return relevant information
    return "Relevant information from vector DB."


def formulate_answer(
    question: str,
    category: str,
) -> str:
    text = f"Kategorie: {category}\n {question}"
    # data = _get_data_from_vector_db(text)
    logger.info("Formulating answer for question: %s", text)

    return "This is a placeholder answer."
