import datetime
import os
from typing import TypeVar
from uuid import uuid4

from app.models.triage import (
    CategorizationResult,
    DaysSinceRequestResponse,
    ProcessingIdResponse,
    TriageResult,
    ZammadTicketModel,
)
from app.utils.logging import getLogger
from dotenv import load_dotenv
from langchain_core.callbacks import Callbacks
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig, RunnableSequence
from langchain_openai import ChatOpenAI
from langfuse import Langfuse, observe
from langfuse.langchain import CallbackHandler
from openai import BadRequestError
from pydantic import SecretStr
from truststore import inject_into_ssl

from .prompts import SYSTEM_PROMPT_CATEGORIES, SYSTEM_PROMPT_DAYS_SINCE_REQUEST
from .settings import ConditionField, ZammadAISettings, get_operator_function
from .ticket_helper import get_articles_by_id

T = TypeVar("T")

load_dotenv()
inject_into_ssl()
logger = getLogger("zammad-ai.triage")


class TriageConfig:
    """Configuration settings for the triage system."""

    # LLM Configuration
    LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
    LITELLM_URL = os.getenv("LITELLM_URL", "")
    LITELLM_MODEL = os.getenv("LITELLM_MODEL", "gpt-4o-mini")

    # Model Parameters
    TEMPERATURE = 0.0
    MAX_RETRIES = 5

    settings = ZammadAISettings()  # type: ignore
    chat_model = ChatOpenAI(
        model=LITELLM_MODEL,
        temperature=TEMPERATURE,
        max_retries=MAX_RETRIES,
        api_key=SecretStr(LITELLM_API_KEY),
        base_url=LITELLM_URL,
    )

    # Langfuse
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "")
    langfuse_handler = CallbackHandler()
    langfuse = Langfuse(public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY, base_url=LANGFUSE_BASE_URL)
    ROLE_DESCRIPTION = langfuse.get_prompt("drivers-licence/role", label="latest").prompt
    EDGE_CASES = langfuse.get_prompt("drivers-licence/edge_cases", label="latest").prompt
    EXAMPLES = langfuse.get_prompt("drivers-licence/examples", label="latest").prompt
    CATEGORIES = langfuse.get_prompt("drivers-licence/categories", label="latest").prompt


async def get_data_from_zammad(id: str) -> ZammadTicketModel:
    """
    Fetch ticket data from Zammad by ticket ID.

    Args:
        id: The ticket ID to fetch
    Returns:
        ZammadTicketModel containing ticket data
    """

    articles = await get_articles_by_id(id)
    ticket = ZammadTicketModel(
        id=id,
        articles=articles if articles else [],
    )
    return ticket


# Cache for the categorization chain to avoid recreation
_categorize_chain: RunnableSequence | None = None


async def _get_categorize_chain() -> RunnableSequence:
    """Get or create the categorization chain with caching."""
    global _categorize_chain

    if _categorize_chain is None:
        categorize_template = ChatPromptTemplate(
            messages=[
                ("system", SYSTEM_PROMPT_CATEGORIES),
                ("user", "{text}"),
            ]
        )

        chat_model = TriageConfig.chat_model

        structured_chat_model: Runnable = chat_model.with_structured_output(schema=CategorizationResult, strict=True)
        _categorize_chain = RunnableSequence(categorize_template, structured_chat_model)

        logger.debug("Categorization chain initialized")

    return _categorize_chain


def _build_config(session_id: str, langfuse_handler: Callbacks | None) -> RunnableConfig:
    config = RunnableConfig(callbacks=[langfuse_handler], metadata={"langfuse_session_id": session_id})  # type: ignore
    return config


def _get_session_id() -> str:
    """Extracts the session id from the request

    Args:
        request (Request): the request

    Returns:
        str: either an existing session_id or creates a new one
    """

    session_id = str(uuid4())
    return session_id


@observe(name="Zammad-AI", as_type="span")
async def category_observer(input, session_id) -> CategorizationResult:
    categorize_chain = await _get_categorize_chain()
    # set session in langfuse trace
    TriageConfig.langfuse.update_current_trace(session_id=session_id)
    config = _build_config(session_id=session_id, langfuse_handler=TriageConfig.langfuse_handler)  # type: ignore
    cat_result: CategorizationResult = await categorize_chain.ainvoke(
        {
            "text": input["text"],
            "role_description": TriageConfig.ROLE_DESCRIPTION,
            "categories": TriageConfig.CATEGORIES,
            "edge_cases": TriageConfig.EDGE_CASES,
            "examples": TriageConfig.EXAMPLES,
        },
        config=config,
    )
    return cat_result


async def predict_category(text: str) -> CategorizationResult:
    """
    Predict the category for the given text using LLM.

    Args:
        text: The text to categorize

    Returns:
        Complete categorization result with category, reasoning, and confidence

    Raises:
        BadRequestError: If the LLM request fails due to content policy
    """
    if not isinstance(text, str) or not text.strip():
        logger.warning("Empty text provided for categorization")
        return CategorizationResult(
            category=None,
            reasoning="Leerer Text kann nicht kategorisiert werden",
            confidence=1.0,
        )

    try:
        cat_result: CategorizationResult = await category_observer(input={"text": text}, session_id=_get_session_id())

        # Log the results
        logger.debug("Text to categorize: %s", text[:100] + "..." if len(text) > 100 else text)
        logger.debug("Category: %s", cat_result.category)
        logger.debug("Reasoning: %s", cat_result.reasoning)
        logger.debug("Confidence: %f", cat_result.confidence)

        # What to do if confidence is low?

        return cat_result

    except BadRequestError as e:
        logger.error("BadRequestError during categorization: %s", e)
        return CategorizationResult(
            category=None,
            reasoning="Fehler: Request konnte nicht vollendet werden, wahrscheinlich wg. Content-Policy",
            confidence=1.0,
        )
    except Exception as e:
        logger.error("Unexpected error during categorization: %s", e)
        return CategorizationResult(
            category=None,
            reasoning=f"Unerwarteter Fehler: {str(e)}",
            confidence=1.0,
        )


async def isAttachement(zammad_data: ZammadTicketModel) -> bool:
    """
    Check if the current request contains attachments.

    Returns:
        True if attachments are present, False otherwise
    """
    if not zammad_data or not zammad_data.articles:
        return False
    for article in zammad_data.articles:
        if article.attachments and len(article.attachments) > 0:
            return True
    return False


async def call_llm(input: dict, system_prompt: str, output: None | type[T]) -> T:
    categorize_template = ChatPromptTemplate(
        messages=[
            ("system", system_prompt),
            ("user", "{text}"),
        ]
    )

    chat_model = TriageConfig.chat_model if output is None else TriageConfig.chat_model.with_structured_output(schema=output, strict=True)

    chain = RunnableSequence(categorize_template, chat_model)
    response = await chain.ainvoke(
        input,
    )
    return response


async def get_action(triage_result: CategorizationResult, zammad_data: ZammadTicketModel | None) -> int:
    """
    Determine the appropriate action based on the categorized text.

    Args:
        category: The predicted category for the text
        text: The original text content

    Returns:
        The recommended action to take
    """
    settings = TriageConfig.settings
    days_since_request = None
    processing_id = None
    # Find matching action rule
    for rule in settings.action_rules:
        if triage_result.category and rule.category_id == triage_result.category.id:
            # If there are conditions, evaluate them
            if rule.conditions:
                conditions = sorted(rule.conditions, key=lambda c: c.priority)
                for condition in conditions:
                    if condition.field == ConditionField.DAYS_SINCE_REQUEST:
                        if days_since_request is None:
                            days_result: DaysSinceRequestResponse = await call_llm(
                                input={
                                    "text": zammad_data.articles[0].text if zammad_data and zammad_data.articles else "",
                                    "today": datetime.datetime.now().strftime("%Y-%m-%d"),
                                },
                                system_prompt=SYSTEM_PROMPT_DAYS_SINCE_REQUEST,
                                output=DaysSinceRequestResponse,
                            )
                            days_since_request = days_result.days_since_request
                        if (get_operator_function(condition.operator))(days_since_request, condition.value):
                            return condition.action_id

                    if condition.field == ConditionField.PROCESSING_ID:
                        if processing_id is None:
                            condition_str = "Processing id " + condition.operator.value + " " + str(condition.value)
                            processing_result: ProcessingIdResponse = await call_llm(
                                input={
                                    "text": zammad_data.articles[0].text if zammad_data and zammad_data.articles else "",
                                    "condition": condition_str,
                                },
                                system_prompt="",  # TODO: Define system prompt for processing_id
                                output=ProcessingIdResponse,
                            )
                            processing_id = processing_result.processing_id
                        if get_operator_function(condition.operator)(processing_id, condition.value):
                            return condition.action_id
            return rule.action_id

    # Default action if no rules matched
    return settings.no_action.id


async def perform_triage(id: str) -> TriageResult:
    """
    Perform complete triage: categorization + action determination.

    Args:
        text: The text to analyze and triage

    Returns:
        Complete triage result with category, action, reasoning, and confidence
    """
    zammad_data = await get_data_from_zammad(id)
    # TODO: Only use the first article or concatenate all articles?
    # Normally the `0` is the customer message, the rest are internal notes
    # But what if there are multiple customer messages? -> edge case
    logger.info("Number of articles in ticket %s: %d", id, len(zammad_data.articles))
    if not zammad_data.articles:
        logger.warning("No articles found for ticket %s", id)
        return TriageResult(
            category=TriageConfig.settings.no_category,
            reasoning="Keine Artikel gefunden",
            confidence=1.0,
            action=TriageConfig.settings.no_action,
        )
    text = zammad_data.articles[0].text

    # Get categorization result
    categorization = await predict_category(text)

    # Determine action based on category
    action_id = await get_action(categorization, zammad_data=zammad_data)
    action = next((a for a in TriageConfig.settings.actions if a.id == action_id), TriageConfig.settings.no_action)

    return TriageResult(
        category=categorization.category if categorization.category else TriageConfig.settings.no_category,
        action=action,
        reasoning=categorization.reasoning,
        confidence=categorization.confidence,
        bearbeitungsstand=categorization.bearbeitungsstand,
        vorangsnummer=categorization.vorgangsnummer,
    )
