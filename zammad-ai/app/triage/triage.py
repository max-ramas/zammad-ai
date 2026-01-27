import datetime
from typing import TypeVar

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from langfuse import observe
from openai import BadRequestError
from truststore import inject_into_ssl

from app.core.settings import Settings, TriageSettings, get_settings
from app.core.triage_settings import (
    Action,
    Category,
    Condition,
    ConditionField,
    ZammadSettings,
)
from app.models.triage import (
    CategorizationResult,
    DaysSinceRequestResponse,
    ProcessingIdResponse,
    TriageResult,
    ZammadTicketModel,
)
from app.observe.observer import _build_config, get_session_id, setup_langfuse
from app.utils.logging import getLogger

from .helper import get_operator_function, id_to_action, id_to_category
from .prompts import SYSTEM_PROMPT_CATEGORIES, SYSTEM_PROMPT_DAYS_SINCE_REQUEST, SYSTEM_PROMPT_PROCESSING_ID
from .ticket_helper import get_data_from_zammad

load_dotenv()
inject_into_ssl()
logger = getLogger("zammad-ai.triage")

T = TypeVar("T")

# Model Parameters
TEMPERATURE = 0.0
MAX_RETRIES = 5


class Triage:
    def __init__(self, settings: None | Settings = None) -> None:
        """Initialize Triage with settings from the global configuration."""
        if settings is not None:
            self.settings: TriageSettings = settings.triage
        else:
            app_settings = get_settings()
            if app_settings.triage is None:
                raise ValueError("Triage settings not configured in application settings")

            self.settings: TriageSettings = app_settings.triage
        self.no_category: Category = id_to_category(self.settings.no_category_id, self.settings.categories, self.settings.no_category_id)
        self.no_action: Action = id_to_action(self.settings.no_action_id, self.settings.actions, self.settings.no_action_id)

        reasoning_config = {}
        if self.settings.openai.reasoning_effort is not None:
            reasoning_config = {"effort": self.settings.openai.reasoning_effort, "summary": "detailed"}
        self.chat_model = ChatOpenAI(
            model=self.settings.openai.completions_model,
            temperature=TEMPERATURE,
            store=False,
            max_retries=MAX_RETRIES,
            api_key=self.settings.openai.api_key,  # type: ignore
            base_url=self.settings.openai.url,
            reasoning=reasoning_config if reasoning_config else None,
        )

        (
            self.langfuse_handler,
            self.langfuse,
            self.ROLE_DESCRIPTION_PROMPT,
            self.EXAMPLES_PROMPT,
            self.CATEGORIES_PROMPT,
        ) = setup_langfuse(self.settings)

    @observe(name="Zammad-AI Triage Predict Category", as_type="span")
    async def call_llm_predict_category(
        self,
        input: dict,
        session_id: str = get_session_id(),
    ) -> CategorizationResult:
        return await self._call_llm(
            input=input,
            system_prompt=SYSTEM_PROMPT_CATEGORIES,
            output=CategorizationResult,
            session_id=session_id,
        )

    @observe(name="Zammad-AI Triage Days Since Request", as_type="span")
    async def call_llm_days_since_request(
        self,
        input: dict,
        session_id: str = get_session_id(),
    ) -> DaysSinceRequestResponse:
        return await self._call_llm(
            input=input,
            system_prompt=SYSTEM_PROMPT_DAYS_SINCE_REQUEST,
            output=DaysSinceRequestResponse,
            session_id=session_id,
        )

    @observe(name="Zammad-AI Triage Processing ID", as_type="span")
    async def call_llm_processing_id(
        self,
        input: dict,
        session_id: str = get_session_id(),
    ) -> ProcessingIdResponse:
        return await self._call_llm(
            input=input,
            system_prompt=SYSTEM_PROMPT_PROCESSING_ID,
            output=ProcessingIdResponse,
            session_id=session_id,
        )

    async def _call_llm(
        self,
        input: dict,
        system_prompt: str,
        output: None | type[T],
        session_id: str = get_session_id(),
    ) -> T:
        categorize_template = ChatPromptTemplate(
            messages=[
                ("system", system_prompt),
                ("user", "{text}"),
            ]
        )
        self.langfuse.update_current_trace(session_id=session_id)
        config = _build_config(session_id=session_id, langfuse_handler=self.langfuse_handler)  # type: ignore

        chat_model = self.chat_model if output is None else self.chat_model.with_structured_output(schema=output, strict=True)

        chain = RunnableSequence(categorize_template, chat_model)
        response = await chain.ainvoke(
            input=input,
            config=config,
        )
        return response

    async def predict_category(self, text: str = "", session_id: str = get_session_id()) -> CategorizationResult:
        """Predict the category of the given text.
        Args:
            text (str): The text to categorize.
        Returns:
            CategorizationResult: The result of the categorization.
        """
        if text.strip() == "":
            logger.warning("Empty text provided for categorization")
            return CategorizationResult(
                category=self.no_category,
                reasoning="Leerer Text kann nicht kategorisiert werden",
                confidence=1.0,
            )

        try:
            cat_result: CategorizationResult = await self.call_llm_predict_category(
                input={
                    "text": text,
                    "role_description": self.ROLE_DESCRIPTION_PROMPT,
                    "categories": self.settings.categories,
                    "categories_prompt": self.CATEGORIES_PROMPT,
                    "examples": self.EXAMPLES_PROMPT,
                },
                session_id=session_id,
            )

            if not cat_result.category or cat_result.category.id not in [c.id for c in self.settings.categories]:
                logger.warning("Predicted category is invalid or not found, assigning no_category")
                cat_result.category = self.no_category
                cat_result.reasoning += " (Kategorie ungültig, 'no_category' zugewiesen)"
                cat_result.confidence = 1.0

            # Log the results
            logger.debug("Text to categorize: %s", text[:100] + "..." if len(text) > 100 else text)
            logger.debug("Category: %s", cat_result.category)
            logger.debug("Reasoning: %s", cat_result.reasoning)
            logger.debug("Confidence: %f", cat_result.confidence)

            return cat_result

        except BadRequestError as e:
            logger.error("BadRequestError during categorization: %s", e)
            return CategorizationResult(
                category=self.no_category,
                reasoning="Fehler: Request konnte nicht vollendet werden, wahrscheinlich wg. Content-Policy",
                confidence=1.0,
            )
        except Exception as e:
            logger.error("Unexpected error during categorization: %s", e)
            return CategorizationResult(
                category=self.no_category,
                reasoning=f"Unerwarteter Fehler: {str(e)}",
                confidence=1.0,
            )

    async def get_action_id(self, categorization_result: CategorizationResult, text: str = "", session_id: str = get_session_id()) -> int:
        """Determine the action ID based on the categorization result and optional text.
        Args:
            categorization_result (CategorizationResult): The result of the categorization.
            text (str, optional): The text to use for evaluating conditions. Defaults to "".
        Returns:
            int: The determined action ID.
        """

        days_since_request = None
        processing_id = None

        # If no category or it's the no_category, always return no_action
        if not categorization_result.category or categorization_result.category.id == self.no_category.id:
            return self.no_action.id

        # Find matching action rule
        for rule in self.settings.action_rules:
            if rule.category_id == categorization_result.category.id:
                # If there are conditions, evaluate them
                if rule.conditions:
                    conditions: list[Condition] = sorted(rule.conditions, key=lambda c: c.priority)
                    for condition in conditions:
                        if condition.field == ConditionField.DAYS_SINCE_REQUEST:
                            if days_since_request is None:
                                days_result: DaysSinceRequestResponse = await self.call_llm_days_since_request(
                                    input={
                                        "text": text,
                                        "today": datetime.datetime.now().strftime("%Y-%m-%d"),
                                    },
                                    session_id=session_id,
                                )
                                days_since_request = days_result.days_since_request
                            if (get_operator_function(operator=condition.operator))(days_since_request, condition.value):
                                return condition.action_id

                        if condition.field == ConditionField.PROCESSING_ID:
                            if processing_id is None:
                                condition_str: str = "Processing id " + condition.operator.value + " " + str(condition.value)
                                processing_result: ProcessingIdResponse = await self.call_llm_processing_id(
                                    input={
                                        "text": text,
                                        "condition": condition_str,
                                    },
                                    session_id=session_id,
                                )
                                processing_id = processing_result.processing_id
                            if get_operator_function(operator=condition.operator)(processing_id, condition.value):
                                return condition.action_id
                return rule.action_id

        # Default action if no rules matched
        return self.no_action.id

    async def perform_triage(self, id: str, settings: ZammadSettings) -> TriageResult:
        """Perform triage on a Zammad ticket by its ID.

        Args:
            id (str): The ID of the Zammad ticket.

        Returns:
            TriageResult: The result of the triage process.
        """
        zammad_data: ZammadTicketModel = await get_data_from_zammad(id, settings=settings)
        # TODO: Only use the first article or concatenate all articles?
        # Normally the `0` is the customer message, the rest are internal notes
        # But what if there are multiple customer messages? -> edge case
        logger.info("Number of articles in ticket %s: %d", id, len(zammad_data.articles))
        if not zammad_data.articles:
            logger.warning("No articles found for ticket %s", id)
            return TriageResult(
                category=self.no_category,
                reasoning="Keine Artikel gefunden",
                confidence=1.0,
                action=self.no_action,
            )
        text = zammad_data.articles[0].text

        # Get categorization result
        categorization: CategorizationResult = await self.predict_category(text)

        # Determine action based on category
        action_id = await self.get_action_id(categorization, text=text)
        action = id_to_action(action_id, self.settings.actions, self.settings.no_action_id)
        return TriageResult(
            category=categorization.category if categorization.category else self.no_category,
            action=action,
            reasoning=categorization.reasoning,
            confidence=categorization.confidence,
        )
