from uuid import uuid4

from langchain_core.callbacks import Callbacks
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.core.triage_settings import TriageSettings


def setup_langfuse(settings: TriageSettings) -> tuple[CallbackHandler, Langfuse, str, str, str]:
    langfuse_handler: CallbackHandler = CallbackHandler()
    langfuse: Langfuse = Langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key,
        base_url=settings.langfuse.base_url,
    )
    ROLE_DESCRIPTION: str = langfuse.get_prompt(settings.prompt_config.role_prompt, label=settings.prompt_config.label).prompt
    EXAMPLES: str = langfuse.get_prompt(settings.prompt_config.examples_prompt, label=settings.prompt_config.label).prompt
    CATEGORIES_PROMPT: str = langfuse.get_prompt(settings.prompt_config.categories_prompt, label=settings.prompt_config.label).prompt
    return langfuse_handler, langfuse, ROLE_DESCRIPTION, EXAMPLES, CATEGORIES_PROMPT


def _build_config(session_id: str, langfuse_handler: Callbacks) -> RunnableConfig:
    config = RunnableConfig(callbacks=[langfuse_handler], metadata={"langfuse_session_id": session_id})  # type: ignore
    return config


def get_session_id() -> str:
    """Generate a unique session ID for Langfuse tracking.
    Returns:
        str: A unique session ID.
    """
    return str(uuid4())
