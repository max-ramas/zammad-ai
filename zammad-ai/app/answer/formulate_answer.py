import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableSequence
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from truststore import inject_into_ssl

from app.models.triage import (
    CategorizationResult,
)
from app.triage.prompts import SYSTEM_PROMPT_ANSWER
from app.utils.logging import getLogger

inject_into_ssl()
load_dotenv()

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "your_qdrant_api_key")
QDRANT_HOST = os.getenv("QDRANT_HOST", "your_qdrant_host")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "your_collection_name")

_formulation_chain = None

LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
LITELLM_URL = os.getenv("LITELLM_URL", "")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "gpt-4o")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

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
            model=LITELLM_MODEL,
            temperature=TEMPERATURE,
            max_retries=MAX_RETRIES,
            api_key=SecretStr(LITELLM_API_KEY),
            base_url=LITELLM_URL,
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
