"""GenAI handler for triage operations.

This module contains all LangChain/GenAI logic for the triage process.
All chains are constructed during initialization for efficient invocation.
"""

from logging import Logger
from typing import Any, TypeVar

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableSequence
from langfuse import observe

from app.core.settings.genai import GenAISettings
from app.models.triage import (
    CategorizationResult,
    DaysSinceRequestResponse,
    ProcessingIdResponse,
)
from app.observe.observer import LangfuseClient
from app.utils.logging import getLogger

logger: Logger = getLogger("zammad-ai.genai_handler")

T = TypeVar("T")


class GenAIHandler:
    """Handles all GenAI/LangChain operations for triage.

    Constructs all chains during initialization and provides clean async methods
    for invoking them with observability support.
    """

    def __init__(self, genai_settings: GenAISettings, prompts: dict[str, str]) -> None:
        """Initialize GenAI handler with chains pre-built.

        Args:
            genai_settings: GenAI configuration (model, temperature, etc.)
            prompts: Dictionary of prompt templates keyed by name:
                - "role": Role description prompt
                - "categories": Categories prompt
                - "examples": Examples prompt
                - "days_since_request": Days since request system prompt
                - "processing_id": Processing ID system prompt

        Raises:
            ValueError: If unsupported GenAI SDK is specified
        """
        self.prompts = prompts
        self.langfuse_client = LangfuseClient()

        # Initialize LLM based on configured SDK
        match genai_settings.sdk:
            case "openai":
                from langchain_openai import ChatOpenAI

                self.chat_model = ChatOpenAI(
                    model=genai_settings.chat_model,  # type: ignore
                    temperature=genai_settings.temperature,
                    max_retries=genai_settings.max_retries,
                    reasoning={
                        "effort": genai_settings.reasoning_effort,
                        "summary": "detailed",
                    }
                    if genai_settings.reasoning_effort is not None
                    else None,
                    store=False,
                )
            case _:
                raise ValueError(f"Unsupported GenAI SDK: {genai_settings.sdk}")

        # Pre-construct chains for each operation
        self._build_chains()

        logger.info("GenAI handler initialized successfully")

    def _build_chains(self) -> None:
        """Build all LangChain chains for reuse."""
        # Category prediction chain
        self.category_chain = RunnableSequence(
            ChatPromptTemplate(
                messages=[
                    ("system", self.prompts.get("categories", "")),
                    ("user", "{text}"),
                ]
            ),
            self.chat_model.with_structured_output(schema=CategorizationResult, strict=True),
        )

        # Days since request extraction chain
        self.days_since_request_chain = RunnableSequence(
            ChatPromptTemplate(
                messages=[
                    ("system", self.prompts.get("days_since_request", "")),
                    ("user", "{text}"),
                ]
            ),
            self.chat_model.with_structured_output(schema=DaysSinceRequestResponse, strict=True),
        )

        # Processing ID extraction chain
        self.processing_id_chain = RunnableSequence(
            ChatPromptTemplate(
                messages=[
                    ("system", self.prompts.get("processing_id", "")),
                    ("user", "{text}"),
                ]
            ),
            self.chat_model.with_structured_output(schema=ProcessingIdResponse, strict=True),
        )

    @observe(name="Zammad-AI Triage Predict Category", as_type="span")
    async def predict_category(
        self,
        input: dict,
        session_id: str | None = None,
    ) -> CategorizationResult:
        """Predict category for the given input.

        Args:
            input: Dictionary with keys:
                - "text": Message text to categorize
                - Additional context as needed
            session_id: Optional Langfuse session ID for tracing

        Returns:
            CategorizationResult with predicted category, reasoning, and confidence
        """
        return await self._invoke_chain(
            chain=self.category_chain,
            input=input,
            session_id=session_id,
        )

    @observe(name="Zammad-AI Triage Days Since Request", as_type="span")
    async def extract_days_since_request(
        self,
        input: dict,
        session_id: str | None = None,
    ) -> DaysSinceRequestResponse:
        """Extract days since request from the given input.

        Args:
            input: Dictionary with keys:
                - "text": Message text to extract from
                - "today": Today's date in YYYY-MM-DD format
            session_id: Optional Langfuse session ID for tracing

        Returns:
            DaysSinceRequestResponse with extracted days value
        """
        return await self._invoke_chain(
            chain=self.days_since_request_chain,
            input=input,
            session_id=session_id,
        )

    @observe(name="Zammad-AI Triage Processing ID", as_type="span")
    async def extract_processing_id(
        self,
        input: dict,
        session_id: str | None = None,
    ) -> ProcessingIdResponse:
        """Extract processing ID from the given input.

        Args:
            input: Dictionary with keys:
                - "text": Message text to extract from
                - "condition": Condition string for ID matching
            session_id: Optional Langfuse session ID for tracing

        Returns:
            ProcessingIdResponse with extracted processing ID
        """
        return await self._invoke_chain(
            chain=self.processing_id_chain,
            input=input,
            session_id=session_id,
        )

    async def _invoke_chain(
        self,
        chain: RunnableSequence[Any, T],
        input: dict,
        session_id: str | None = None,
    ) -> T:
        """Invoke a pre-built chain with observability support.

        Args:
            chain: The RunnableSequence chain to invoke
            input: Input dictionary for the chain
            session_id: Optional Langfuse session ID for tracing

        Returns:
            The chain's output
        """
        if session_id is None:
            session_id = self.langfuse_client.generate_session_id()

        self.langfuse_client.langfuse.update_current_trace(session_id=session_id)
        config: RunnableConfig = self.langfuse_client.build_config(session_id=session_id)

        response: T = await chain.ainvoke(input=input, config=config)
        return response
