import os
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.callbacks import Callbacks
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

load_dotenv()

# Langfuse
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "")
LANGFUSE_PROMPT_LABEL = os.getenv("LANGFUSE_PROMPT_LABEL", "latest")


def setup_langfuse() -> tuple[CallbackHandler, Langfuse, str, str, str, str]:
    langfuse_handler: CallbackHandler = CallbackHandler()
    langfuse: Langfuse = Langfuse(public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY, base_url=LANGFUSE_BASE_URL)
    ROLE_DESCRIPTION: str = langfuse.get_prompt("drivers-licence/role", label=LANGFUSE_PROMPT_LABEL).prompt
    EDGE_CASES: str = langfuse.get_prompt("drivers-licence/edge_cases", label=LANGFUSE_PROMPT_LABEL).prompt
    EXAMPLES: str = langfuse.get_prompt("drivers-licence/examples", label=LANGFUSE_PROMPT_LABEL).prompt
    CATEGORIES_PROMPT: str = langfuse.get_prompt("drivers-licence/categories", label=LANGFUSE_PROMPT_LABEL).prompt
    return langfuse_handler, langfuse, ROLE_DESCRIPTION, EDGE_CASES, EXAMPLES, CATEGORIES_PROMPT


def _build_config(session_id: str, langfuse_handler: Callbacks) -> RunnableConfig:
    config = RunnableConfig(callbacks=[langfuse_handler], metadata={"langfuse_session_id": session_id})  # type: ignore
    return config


def _get_session_id() -> str:
    """Extracts the session id from the request

    Args:
        request (Request): the request

    Returns:
        str: either an existing session_id or creates a new one
    """
    return str(uuid4())
