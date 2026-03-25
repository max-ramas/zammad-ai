from logging import Logger
from time import perf_counter

from langchain.agents.middleware.types import AgentState
from langchain.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from prometheus_client import Gauge, Histogram

from app.observe import LangfuseClient, LangfuseError
from app.settings import ZammadAISettings
from app.settings.answer import FileAnswerPrompt, LangfuseAnswerPrompt, StringAnswerPrompt
from app.utils.logging import getLogger
from app.utils.paths import get_prompts_dir
from app.utils.prompts import load_prompt

from .agent import AgentContext, StructuredAgentResponse, build_agent
from .dlf import DLFClient
from .knowledgebase import QdrantKBClient

logger: Logger = getLogger("zammad-ai.answer.service")

ANSWER_RUN_DURATION_SECONDS = Histogram(
    name="zammad_ai_answer_run_duration_seconds",
    documentation="Duration of answer service runs in seconds.",
    labelnames=("outcome",),
)

ANSWER_RUNS_IN_PROGRESS = Gauge(
    name="zammad_ai_answer_runs_in_progress",
    documentation="Number of answer runs currently in progress.",
)


class AnswerService:
    def __init__(self, settings: ZammadAISettings) -> None:
        # Optionally set up Langfuse client if enabled in settings
        """
        Initialize the AnswerService, configuring prompt sources, the agent, and supporting clients from the provided settings.

        The initializer:
        - Optionally creates a Langfuse client when langfuse is enabled.
        - Resolves the agent system prompt from one of: Langfuse, a file, or a string in settings.
        - Loads the user message template from the prompts directory.
        - Builds the compiled agent graph using genai settings and the resolved system prompt.
        - Creates a Qdrant knowledge-base client and an optional DLF client.
        - Assembles the AgentContext with the KB and DLF clients.

        Parameters:
            settings (ZammadAISettings): Configuration used to enable integrations and supply prompts, GenAI, Qdrant, and DLf settings.

        Raises:
            ValueError: If Langfuse is referenced as the prompt source but Langfuse is not enabled in settings.
            ValueError: If `settings.answer.agent_prompt` is not a supported prompt source type.

        Notes:
            If fetching the prompt from Langfuse fails, the process exits with status code 1.
        """
        self.settings: ZammadAISettings = settings

        self.langfuse_client: LangfuseClient | None = None
        if settings.langfuse_enabled:
            self.langfuse_client = LangfuseClient()

        # Get the system prompt for the answer agent from settings, supporting multiple sources (Langfuse, file, or string)
        agent_prompt: str
        if isinstance(settings.answer.agent_prompt, LangfuseAnswerPrompt):
            if self.langfuse_client is None:
                raise ValueError("Langfuse must be enabled in settings to use it as a prompt source.")
            try:
                agent_prompt: str = self.langfuse_client.get_prompt(
                    prompt_name=settings.answer.agent_prompt.prompt.name,
                    prompt_label=settings.answer.agent_prompt.prompt.label,
                )
            except LangfuseError:
                logger.error("Failed to fetch agent prompt from Langfuse, exiting.", exc_info=True)
                exit(1)
        elif isinstance(settings.answer.agent_prompt, FileAnswerPrompt):
            agent_prompt = load_prompt(file_path=settings.answer.agent_prompt.prompt)
        elif isinstance(settings.answer.agent_prompt, StringAnswerPrompt):
            agent_prompt = settings.answer.agent_prompt.prompt
        else:
            raise ValueError("Invalid type for answer.agent_prompt in settings.")

        # Setup the user message template as an object variable
        self.user_message_template: PromptTemplate = PromptTemplate.from_template(
            template=load_prompt(file_path=get_prompts_dir() / "answer" / "user_message_template.prompt.md"),
        )

        self.agent: CompiledStateGraph[
            AgentState[StructuredAgentResponse], AgentContext, AgentState, AgentState[StructuredAgentResponse]  # type: ignore
        ] = build_agent(
            genai_settings=settings.genai,
            system_prompt=agent_prompt,
            dlf_enabled=settings.answer.dlf is not None,
        )
        self.qdrant_kb_client = QdrantKBClient(
            genai_settings=settings.genai,
            qdrant_settings=settings.answer.qdrant,
        )
        self.dlf_client: DLFClient | None = DLFClient(dlf_settings=settings.answer.dlf) if settings.answer.dlf is not None else None
        self.agent_context: AgentContext = AgentContext(
            qdrant_kb_client=self.qdrant_kb_client,
            dlf_client=self.dlf_client,
        )

    async def generate_answer(
        self,
        user_text: str,
        category: str,
        session_id: str | None = None,
    ) -> StructuredAgentResponse:
        """
        Generate a structured answer for the given user text and category, optionally associating the request with a provided Langfuse session.

        Parameters:
            user_text (str): The user's input text to be answered.
            category (str): The category or topic context to include in the user message.
            session_id (str | None): Optional session identifier used for Langfuse tracing; if omitted and Langfuse is enabled, a session id will be generated.

        Returns:
            StructuredAgentResponse: The agent's structured response containing the answer and associated metadata (for example retrieval context and tracing information).
        """
        start_time: float = perf_counter()
        outcome: str = "error"
        ANSWER_RUNS_IN_PROGRESS.inc()
        logger.debug(f"Answer generation with payload:\nuser_text: {user_text}\ncategory: {category}")
        try:
            if session_id is None and self.langfuse_client is not None:
                session_id = self.langfuse_client.generate_session_id()
            user_message = HumanMessage(
                content=self.user_message_template.format(
                    user_text=user_text,
                    category=category,
                )
            )
            config: RunnableConfig = (
                self.langfuse_client.build_config(session_id=session_id) if self.langfuse_client is not None else RunnableConfig()
            )
            agent_result: dict = await self.agent.ainvoke(
                input={"messages": [user_message]},
                config=config,
                context=self.agent_context,
            )
            logger.debug(f"Agent raw result:\n{agent_result}")
            structured_response = agent_result["structured_response"]
            if self.settings.answer.ai_answer_disclaimer.strip() != "":
                structured_response.response += f"\n\n{self.settings.answer.ai_answer_disclaimer}"
            outcome = "success"
            return structured_response
        finally:
            ANSWER_RUN_DURATION_SECONDS.labels(outcome=outcome).observe(perf_counter() - start_time)
            ANSWER_RUNS_IN_PROGRESS.dec()

    async def cleanup(self) -> None:
        """
        Close internal clients and reset the module-level service reference.

        Attempts to close the Qdrant KB client and, if present, the DLF client. Always resets the module-level `_service` reference to `None` so the service can be recreated.
        """
        try:
            await self.qdrant_kb_client.close()
            if self.dlf_client is not None:
                await self.dlf_client.close()
        finally:
            global _service
            _service = None


_service: AnswerService | None = None


def get_answer_service(settings: ZammadAISettings | None = None) -> AnswerService:
    """
    Get or create the shared AnswerService instance.

    Args:
        settings: Optional settings to initialize the AnswerService instance.
                 If not provided, uses get_settings().

    Returns:
        AnswerService: The shared AnswerService instance.
    """
    global _service
    if _service is None:
        if settings is None:
            from app.settings import get_settings

            settings = get_settings()
        _service = AnswerService(settings=settings)
    return _service
